import csv
from collections import defaultdict

# Priority of email sources
PRIORITY = {
    "bio": 1,
    "site": 2,
    "site_deep": 3,
    "guess_personal": 4
}

def priority_value(source):
    return PRIORITY.get(source, 99)


def is_valid_email(email):
    if not email: 
        return False
    if "example.com" in email.lower(): 
        return False
    if email.strip() == "":
        return False
    if "@" not in email:
        return False
    return True


def is_error_row(row):
    # Remove rows that failed to scrape
    if row["source"] == "error":
        return True
    if "profile_error" in row.get("smtp_note", ""):
        return True
    return False


def load_rows():
    with open("emails.csv", "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return list(reader)


def clean_rows(rows):
    cleaned = []

    for r in rows:
        # Skip error rows
        if is_error_row(r):
            continue

        # Skip invalid emails
        if not is_valid_email(r["email"]):
            continue

        cleaned.append(r)

    return cleaned


def select_best(cleaned_rows):
    best = {}

    for row in cleaned_rows:
        user = row["username"]

        if user not in best:
            best[user] = row
            continue

        # If new row has *better* source priority, replace
        if priority_value(row["source"]) < priority_value(best[user]["source"]):
            best[user] = row

    return list(best.values())


def save_output(rows):
    if not rows:
        print("[!] No rows to save!")
        return

    with open("emails_clean.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    print(f"[✓] Saved {len(rows)} final cleaned rows → emails_clean.csv")


def main():
    print("[i] Loading emails.csv…")
    rows = load_rows()
    print(f"[i] Loaded {len(rows)} rows.")

    print("[i] Removing errors + invalid emails…")
    valid_rows = clean_rows(rows)
    print(f"[✓] {len(rows)} → {len(valid_rows)} valid rows.")

    print("[i] Selecting best email per user…")
    final = select_best(valid_rows)
    print(f"[✓] Unique users: {len(final)}")

    save_output(final)


if __name__ == "__main__":
    main()