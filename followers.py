#!/usr/bin/env python3
import time
import random
import argparse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options


# -------------------------------------------------------
# HUMAN SLEEP
# -------------------------------------------------------
def human_sleep(a=0.8, b=1.7):
    time.sleep(random.uniform(a, b))


# -------------------------------------------------------
# CONNECT TO EXISTING CHROME SESSION
# -------------------------------------------------------
def get_browser():
    print("[i] Connecting to existing Chrome (debugger mode)…")
    chrome_options = Options()
    chrome_options.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    browser = webdriver.Chrome(options=chrome_options)
    return browser


# -------------------------------------------------------
# CLICK FOLLOWERS BUTTON
# -------------------------------------------------------
def click_followers_button(browser, username):

    print("[i] Trying multiple ways to click followers button…")

    XPATHS = [
        "//a[contains(@href,'/followers')]",
        "//a[contains(text(),'Followers')]",
        "//a[contains(text(),'followers')]",
        "//span[contains(text(),'followers')]/ancestor::a",
        "//span[contains(text(),'Followers')]/ancestor::a",
        "//button[contains(text(),'Followers')]",
        "//*[@aria-label='Followers']"
    ]

    for xp in XPATHS:
        try:
            el = browser.find_element(By.XPATH, xp)
            browser.execute_script("arguments[0].click();", el)
            human_sleep(2, 3)
            print("[✓] Followers clicked via:", xp)
            return True
        except:
            continue

    # Last fallback
    try:
        browser.execute_script("""
            [...document.querySelectorAll('*')].forEach(el=>{
                if(el.innerText && el.innerText.toLowerCase().includes('followers')){
                    el.click();
                }
            });
        """)
        human_sleep(3, 4)
        print("[✓] Followers clicked via JS fallback")
        return True
    except:
        pass

    return False


# -------------------------------------------------------
# FIND REAL SCROLL CONTAINER (Auto-detection)
# -------------------------------------------------------
# -------------------------------------------------------
# FIND REAL SCROLL CONTAINER BASED ON YOUR INSTAGRAM DOM
# -------------------------------------------------------
def detect_scroll_container(browser):
    print("[i] Detecting followers scroll container…")

    # Wait few seconds for popup to fully render
    time.sleep(2)

    # 1️⃣ FIRST: Grab the followers popup dialog
    dialogs = browser.find_elements(By.CSS_SELECTOR, "div[role='dialog']")
    if not dialogs:
        raise Exception("❌ Followers dialog NOT found!")

    popup = dialogs[-1]  # Usually the last dialog is the followers popup
    print("[✓] Followers popup dialog detected")

    # 2️⃣ Grab ALL divs inside popup
    all_divs = popup.find_elements(By.XPATH, ".//div")

    # 3️⃣ Find the FIRST div whose scrollTop changes when we scroll it
    print("[i] Searching inside popup for real scroll container…")

    for div in all_divs:
        try:
            height = div.size.get("height", 0)
            if height < 200:  # too small to be scrollable
                continue

            before = browser.execute_script("return arguments[0].scrollTop;", div)
            browser.execute_script("arguments[0].scrollTop = arguments[0].scrollTop + 300;", div)
            time.sleep(0.2)
            after = browser.execute_script("return arguments[0].scrollTop;", div)

            if after > before:  # scroll actually moved → this is our container
                print("[⭐] FOUND scrollable container!")
                print("   scrollTop changed:", before, "→", after)
                return div

        except Exception:
            continue

    raise Exception("❌ NO scrollable div found inside followers popup!")


# -------------------------------------------------------
# SCROLL + EXTRACT (final working version)
# -------------------------------------------------------
def scroll_and_extract(browser, container, limit):
    print("[i] Extracting followers…")

    followers = set()
    stagnant = 0
    last_count = 0

    while len(followers) < limit and stagnant < 15:

        # extract usernames from visible items
        links = container.find_elements(By.TAG_NAME, "a")
        for link in links:
            href = link.get_attribute("href")
            if not href or "/p/" in href:
                continue
            try:
                user = href.split("/")[-2]
                if user:
                    followers.add(user)
            except:
                pass

        print(f"[i] Extracted so far: {len(followers)}")

        # perform smooth scroll
        browser.execute_script("arguments[0].scrollTop += 600;", container)
        human_sleep(1.1, 2.0)

        # stagnation detection
        if len(followers) == last_count:
            stagnant += 1
        else:
            stagnant = 0

        last_count = len(followers)

    print("[i] Scrolling finished.")
    return list(followers)


# -------------------------------------------------------
# SAVE TO FILE
# -------------------------------------------------------
def save_followers(lst):
    with open("followers.txt", "w", encoding="utf-8") as f:
        for u in lst:
            f.write(u + "\n")
    print(f"[✓] Saved {len(lst)} followers → followers.txt")


# -------------------------------------------------------
# MAIN
# -------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--limit", default=2000, type=int)
    args = parser.parse_args()

    print("\n🚀 Starting INSTAGRAM Bulletproof Extractor…\n")

    browser = get_browser()

    url = f"https://www.instagram.com/{args.user}/"
    browser.get(url)
    human_sleep(3, 4)

    if not click_followers_button(browser, args.user):
        raise Exception("❌ Could not click Followers button")

    human_sleep(3, 4)

    container = detect_scroll_container(browser)

    followers = scroll_and_extract(browser, container, args.limit)

    save_followers(followers)


if __name__ == "__main__":
    main()