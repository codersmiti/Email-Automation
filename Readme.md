# Email Extraction Pipeline

This project fetches all followers of any Instagram account, extracts possible emails from their bios or linked websites, and produces a cleaned CSV containing the best email per user.

---

## 🚀 How to Run

1. Create and Activate Virtual Environment
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
2. Start Chrome in Debugger Mode
```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="chrome-data"
```
Keep this Chrome window open. Selenium will attach to it.

3. Fetch all followers of any account
```bash
python followers.py --user INSTAGRAM_USERNAME --limit 2000
```
This generates followers.txt

4. Extract emails by scanning bio, website link, and deep links
```bash
python scrape_emails.py
```
This generates emails.csv

5. Select the best email per user
```bash
python cleaner.py
```
This generates cleaned_emails.csv

6. Dry Run (No emails actually sent)
```bash
python sender.py --csv cleaned_emails.csv --dry-run
```
Shows what would be sent and logs everything

7. Send Real Emails
```bash
python sender.py --csv cleaned_emails.csv --from-email your@gmail.com --from-pass YOUR_APP_PASSWORD --subject "Optional default subject"
```
The script will auto-generate a personal subject, auto-generate a DM-style message body, send one email per user and log everything

8. (OPTIONAL) Only send to verified emails (MX + SMTP checks)
```bash
python sender.py --csv cleaned_emails.csv --only-verified
```

9. If you want to limit the emails
```bash
python sender.py --limit 50
```

