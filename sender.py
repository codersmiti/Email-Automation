#!/usr/bin/env python3
import argparse, csv, json, os, random, smtplib
from email.mime.text import MIMEText
from email.utils import formataddr
from openpyxl import Workbook

def generate_subject(full_name: str, username: str):
    first = full_name.split()[0] if full_name else username

    subjects = [
        f"A quick note for {first}",
        f"Something small for you, {first}",
        f"This reminded me of you, {first}",
        f"Hey {first}",
        f"A thought you might like, {first}",
        f"Your content made me think of this, {first}",
        f"A tiny journaling thought, {first}",
        f"Made me think of your page, {first}",
        f"Hi {first}",
        f"Sharing something with you, {first}",
    ]
    return random.choice(subjects)

# DM-style short email text, includes "Sentari AI" exactly once and varies tone.
def generate_dm_style_email(to_user: str, personalization: str = "") -> str:
    variants = [
        "Hey @{u}, fellow journaling nerd here — I’ve been using Sentari AI and it’s helped me notice little shifts in mood and habits. {p}",
        "Hi @{u}! I love how you share reflective posts — thought you might vibe with Sentari AI; it’s a gentle journaling companion for personal growth. {p}",
        "Hey @{u}, your page gave me cozy notebook energy 📖 Lately I’ve been trying Sentari AI to track mood threads — it’s been surprisingly grounding. {p}",
        "Hi @{u} 🌿 I’m a journaling fan too, and Sentari AI nudged me into more mindful check-ins — figured I’d share in case it sparks anything. {p}",
        "Hey @{u}! I’m curious how you keep up your journaling rhythm — I’ve been leaning on Sentari AI and enjoying the reflective prompts. {p}",
        "Hi @{u} 💭 Your content feels super thoughtful — sharing Sentari AI since it’s helped me reflect without the pressure to be ‘perfect.’ {p}",
    ]
    msg = random.choice(variants).format(u=to_user or "there", p=personalization or "").strip()
    return " ".join(msg.split())

def send_email(smtp_server, smtp_port, sender_email, sender_name, sender_pass, to_email, subject, body):
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = formataddr((sender_name, sender_email))
    msg["To"] = to_email

    with smtplib.SMTP(smtp_server, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_pass)
        server.sendmail(sender_email, [to_email], msg.as_string())

def main():
    ap = argparse.ArgumentParser(description="Send personalized emails and log delivery status.")
    ap.add_argument("--csv", default="emails.csv", help="Input CSV from scraper")
    ap.add_argument("--out-json", default="email_status.json", help="Output JSON log")
    ap.add_argument("--out-xlsx", default="email_status.xlsx", help="Output Excel log")
    ap.add_argument("--only-verified", action="store_true", help="Send only if mx==True and smtp_status in {accepted, unknown}")
    ap.add_argument("--limit", type=int, default=100, help="Max emails to send this run")
    ap.add_argument("--smtp-server", default=os.getenv("SMTP_SERVER","smtp.gmail.com"))
    ap.add_argument("--smtp-port", type=int, default=int(os.getenv("SMTP_PORT","587")))
    ap.add_argument("--from-email", default=os.getenv("SENDER_EMAIL","you@example.com"))
    ap.add_argument("--from-name", default=os.getenv("SENDER_NAME","A friendly journaling fan"))
    ap.add_argument("--from-pass", default=os.getenv("SENDER_PASS",""))
    ap.add_argument("--dry-run", action="store_true", help="Do not actually send; just generate messages and logs")
    args = ap.parse_args()

    if not args.dry_run and not args.from_pass:
        raise SystemExit("Missing sender password. Pass via --from-pass or SENDER_PASS env var.")

    # Read CSV
    rows = []
    with open(args.csv, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            email = (r.get("email") or "").strip()
            if not email:
                continue
            rows.append(r)

    # Filter & limit
    selected, seen = [], set()
    for r in rows:
        em = r["email"].lower()
        if em in seen: continue
        if args.only_verified:
            mx_ok = r.get("mx","").lower() == "true"
            smtp_ok = r.get("smtp_status","") in ("accepted","unknown")
            if not (mx_ok and smtp_ok):
                continue
        seen.add(em)
        selected.append(r)
        if len(selected) >= args.limit:
            break

    print(f"[i] Sending to {len(selected)} recipients (limit={args.limit}, only_verified={args.only_verified})")

    wb = Workbook()
    ws = wb.active
    ws.title = "EmailStatus"
    ws.append(["username","email","full_name","sent_status","note","preview_body"])

    log = []
    for r in selected:
        username = r.get("username") or ""
        to_email = r.get("email") or ""
        full_name = r.get("full_name") or username
        personalization = ""  # plug in your own heuristics if you store bios/domains

        body = generate_dm_style_email(username or full_name, personalization)
        subject = generate_subject(full_name, username)

        sent = "dry_run" if args.dry_run else "failed"
        note = ""
        try:
            if not args.dry_run:
                send_email(args.smtp_server, args.smtp_port, args.from_email, args.from_name, args.from_pass, to_email, subject, body)
                sent = "success"
        except Exception as e:
            sent = "failed"
            note = type(e).__name__

        ws.append([username, to_email, full_name, sent, note, body])
        log.append({"username":username,"email":to_email,"full_name":full_name,"sent_status":sent,"note":note,"preview_body":body})

    wb.save(args.out_xlsx)
    with open(args.out_json, "w", encoding="utf-8") as jf:
        json.dump(log, jf, indent=2, ensure_ascii=False)

    print(f"[✓] Logged to {args.out_xlsx} and {args.out_json}")

if __name__ == "__main__":
    main()
