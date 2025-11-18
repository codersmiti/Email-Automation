# Email Extraction Pipeline

This project fetches all followers of any Instagram account, extracts possible emails from their bios or linked websites, and produces a cleaned CSV containing the best email per user.

---

## 🚀 How to Run

1. Create and Activate Virtual Environment**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```
2. Start Chrome in Debugger Mode
chrome.exe --remote-debugging-port=9222 --user-data-dir="chrome-data"
```
Keep this Chrome window open. Selenium will attach to it.
