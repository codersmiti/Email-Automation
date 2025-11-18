#!/usr/bin/env python3
import argparse
import csv
import json
import re
import time
import socket
from typing import Set
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
import instaloader
import tldextract
import dns.resolver
import smtplib

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
MAILTO_REGEX = re.compile(r"mailto:([^?]+)")
OBFUSCATION = re.compile(
    r"\s*\[\s*at\s*\]\s*|\s*\(\s*at\s*\)\s*|\s+at\s+|\s*\[dot\]\s*|\s*\(\s*dot\s*\)\s*|\s+dot\s+",
    re.IGNORECASE,
)

# Link-in-bio / aggregator services (bad for guessing)
AGGREGATOR_DOMAINS = {
    "linktr.ee",
    "bio.site",
    "beacons.ai",
    "bit.ly",
    "campsite.bio",
    "msha.ke",
    "withkoji.com",
    "stan.store",
}

# Social / platforms (also bad for guessing)
SOCIAL_DOMAINS = {
    "instagram.com",
    "facebook.com",
    "fb.com",
    "youtube.com",
    "youtu.be",
    "tiktok.com",
    "x.com",
    "twitter.com",
    "pinterest.com",
    "patreon.com",
    "substack.com",
}


def clean_obfuscated_email(text: str) -> str:
    t = OBFUSCATION.sub(
        lambda m: "@" if "at" in m.group(0).lower() else ".", text or ""
    )
    return (
        (t or "")
        .replace(" [at] ", "@")
        .replace(" (at) ", "@")
        .replace(" [dot] ", ".")
        .replace(" (dot) ", ".")
    )


def extract_emails_from_text(text: str) -> Set[str]:
    text = clean_obfuscated_email(text or "")
    return {m.group(0) for m in EMAIL_REGEX.finditer(text)}


def domain_from_url(url: str):
    if not url:
        return None
    ext = tldextract.extract(url)
    if not ext.domain or not ext.suffix:
        return None
    return f"{ext.domain}.{ext.suffix}"


def mx_exists(domain: str) -> bool:
    try:
        dns.resolver.resolve(domain, "MX")
        return True
    except Exception:
        return False


def guess_emails(full_name: str, domain: str) -> Set[str]:
    if not domain or not full_name:
        return set()
    name = re.sub(r"[^a-zA-Z\s]", "", full_name).strip().lower()
    if not name:
        return set()
    parts = [p for p in name.split() if p]
    first = parts[0]
    last = parts[-1] if len(parts) > 1 else ""
    fl = first[0] if first else ""
    ll = last[0] if last else ""

    bases = set()
    if last:
        bases |= {
            f"{first}.{last}",
            f"{first}{last}",
            f"{fl}{last}",
            f"{first}{ll}",
            f"{first}_{last}",
            f"{first}-{last}",
        }
    bases.add(first)

    return {f"{b}@{domain}" for b in bases}


def http_get(url: str, timeout: int = 12):
    headers = {"User-Agent": "Mozilla/5.0 (compatible; OutreachBot/1.0)"}
    return requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)


def extract_emails_and_links_from_url(url: str, max_bytes: int):
    """
    Fetch a page, extract:
    - emails from text + mailto links
    - all regular links (for deeper crawling)
    """
    emails = set()
    links: Set[str] = set()
    try:
        h = requests.head(url, timeout=8, allow_redirects=True)
        size = int(h.headers.get("Content-Length", "0") or 0)
        if size and size > max_bytes:
            return set(), set(), f"skip_large:{size}"
        r = http_get(url)
        if r.status_code >= 400:
            return set(), set(), f"http_{r.status_code}"
        soup = BeautifulSoup(r.text, "html.parser")

        # mailto links
        for a in soup.select('a[href^="mailto:"]'):
            href = a.get("href", "")
            m = MAILTO_REGEX.search(href)
            if m:
                emails.add(m.group(1))

        # visible text + meta
        blob = " ".join(
            [soup.get_text(separator=" ", strip=True)]
            + [m.get("content", "") for m in soup.find_all("meta")]
        )
        emails |= extract_emails_from_text(blob)

        # regular links for deep crawl
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.startswith("#") or href.startswith("mailto:"):
                continue
            full = urljoin(r.url, href)
            links.add(full)

        return emails, links, "ok"
    except Exception as e:
        return set(), set(), f"error:{type(e).__name__}"


def smtp_handshake_check(
    email: str, mail_from: str = "noreply@example.com", timeout: int = 8
):
    """
    Best-effort SMTP RCPT check.
    NOTE: On Windows, outbound port 25 is usually blocked → use without --smtp-verify.
    """
    try:
        _, domain = email.split("@", 1)
    except ValueError:
        return "unknown", "bad_email"
    try:
        answers = dns.resolver.resolve(domain, "MX")
        mx_hosts = [r.exchange.to_text(omit_final_dot=True) for r in answers]
    except Exception:
        return "unknown", "no_mx"

    for host in mx_hosts:
        try:
            with smtplib.SMTP(host, 25, timeout=timeout) as s:
                s.helo("example.com")
                s.mail(mail_from)
                code, _ = s.rcpt(email)
                if 200 <= code < 300:
                    return "accepted", f"{host}"
                elif 500 <= code < 600:
                    return "refused", f"{host}:{code}"
                else:
                    return "unknown", f"{host}:{code}"
        except (smtplib.SMTPException, socket.timeout, ConnectionError):
            continue
    return "unknown", "mx_unreachable"


def load_usernames(path: str):
    users = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            users.append(s.lstrip("@"))
    return users


def is_aggregator_or_social(domain: str) -> bool:
    return domain in AGGREGATOR_DOMAINS or domain in SOCIAL_DOMAINS


def main():
    ap = argparse.ArgumentParser(
        description=(
            "Scrape Instagram bios + external sites for emails with deep crawling and "
            "safer guessing (no more first.last@linktr.ee)."
        )
    )
    ap.add_argument("--usernames", required=True, help="Path to usernames.txt")
    ap.add_argument("--out", default="emails.csv", help="Output CSV")
    ap.add_argument("--json", default="emails.json", help="Output JSON")
    ap.add_argument("--sleep", type=float, default=2.0, help="Delay between profiles")
    ap.add_argument(
        "--max-site-bytes",
        type=int,
        default=1_000_000,
        help="Skip site if larger than this",
    )
    ap.add_argument(
        "--smtp-verify",
        action="store_true",
        help="Attempt SMTP RCPT handshake (may be blocked on Windows)",
    )
    ap.add_argument("--login-user", default=None, help="Instagram login username")
    ap.add_argument("--login-pass", default=None, help="Instagram login password")
    ap.add_argument(
        "--max-deep-links",
        type=int,
        default=5,
        help="Max deep links to follow per profile",
    )
    args = ap.parse_args()

    L = instaloader.Instaloader(
        download_pictures=False,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
    )

    if args.login_user:
        try:
            if args.login_pass:
                L.login(args.login_user, args.login_pass)
            else:
                L.interactive_login(args.login_user)
            print("[i] Logged in.")
        except Exception as e:
            print(f"[!] Login failed: {e} — continuing without login.")

    users = load_usernames(args.usernames)
    if not users:
        print("No usernames found.")
        return

    rows = []
    with open(args.out, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "username",
                "full_name",
                "external_url",
                "email",
                "source",
                "mx",
                "smtp_status",
                "smtp_note",
            ],
        )
        writer.writeheader()

        for u in users:
            time.sleep(args.sleep)
            print(f"[i] {u}")
            try:
                profile = instaloader.Profile.from_username(L.context, u)
            except Exception as e:
                row = {
                    "username": u,
                    "full_name": "",
                    "external_url": "",
                    "email": "",
                    "source": "error",
                    "mx": "",
                    "smtp_status": "",
                    "smtp_note": f"profile_error:{type(e).__name__}",
                }
                rows.append(row)
                writer.writerow(row)
                continue

            full_name = profile.full_name or ""
            bio = profile.biography or ""
            ext_url = profile.external_url or ""

            # 1) Bio emails (highest confidence)
            for em in extract_emails_from_text(bio):
                mx_ok = mx_exists(em.split("@")[-1])
                smtp_status, smtp_note = ("", "")
                if args.smtp_verify and mx_ok:
                    smtp_status, smtp_note = smtp_handshake_check(em)
                row = {
                    "username": u,
                    "full_name": full_name,
                    "external_url": ext_url,
                    "email": em,
                    "source": "bio",
                    "mx": str(mx_ok),
                    "smtp_status": smtp_status,
                    "smtp_note": smtp_note,
                }
                rows.append(row)
                writer.writerow(row)

            if not ext_url:
                continue

            # 2) First-level external URL: emails + outbound links
            site_emails, links, note = extract_emails_and_links_from_url(
                ext_url, args.max_site_bytes
            )
            for em in site_emails:
                mx_ok = mx_exists(em.split("@")[-1])
                smtp_status, smtp_note = ("", "")
                if args.smtp_verify and mx_ok:
                    smtp_status, smtp_note = smtp_handshake_check(em)
                row = {
                    "username": u,
                    "full_name": full_name,
                    "external_url": ext_url,
                    "email": em,
                    "source": "site",
                    "mx": str(mx_ok),
                    "smtp_status": smtp_status,
                    "smtp_note": smtp_note,
                }
                rows.append(row)
                writer.writerow(row)

            # 3) Deep crawl non-aggregator, non-social links to find REAL sites
            candidate_domains = {}
            for link in links:
                d = domain_from_url(link)
                if not d or is_aggregator_or_social(d):
                    continue
                if d not in candidate_domains:
                    candidate_domains[d] = link

            deep_count = 0
            personal_domains = set()
            for dom, link in candidate_domains.items():
                if deep_count >= args.max_deep_links:
                    break
                deep_count += 1
                deep_emails, _, dnote = extract_emails_and_links_from_url(
                    link, args.max_site_bytes
                )
                if deep_emails:
                    personal_domains.add(dom)
                for em in deep_emails:
                    mx_ok = mx_exists(em.split("@")[-1])
                    smtp_status, smtp_note = ("", "")
                    if args.smtp_verify and mx_ok:
                        smtp_status, smtp_note = smtp_handshake_check(em)
                    row = {
                        "username": u,
                        "full_name": full_name,
                        "external_url": link,
                        "email": em,
                        "source": "site_deep",
                        "mx": str(mx_ok),
                        "smtp_status": smtp_status,
                        "smtp_note": smtp_note,
                    }
                    rows.append(row)
                    writer.writerow(row)

            # 4) Guess emails ONLY on domains that already yielded at least one email
            for dom in personal_domains:
                if not mx_exists(dom):
                    continue
                for em in sorted(guess_emails(full_name, dom)):
                    mx_ok = mx_exists(em.split("@")[-1])
                    smtp_status, smtp_note = ("", "")
                    if args.smtp_verify and mx_ok:
                        smtp_status, smtp_note = smtp_handshake_check(em)
                    row = {
                        "username": u,
                        "full_name": full_name,
                        "external_url": f"https://{dom}",
                        "email": em,
                        "source": "guess_personal",
                        "mx": str(mx_ok),
                        "smtp_status": smtp_status,
                        "smtp_note": smtp_note,
                    }
                    rows.append(row)
                    writer.writerow(row)

    with open(args.json, "w", encoding="utf-8") as jf:
        json.dump(rows, jf, indent=2, ensure_ascii=False)

    print(f"[✓] Wrote {len(rows)} rows -> {args.out} and {args.json}")


if __name__ == "__main__":
    main()
