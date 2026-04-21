import requests
from bs4 import BeautifulSoup
import json, time, os

TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]
COOKIE = os.environ["SESSION_COOKIE"]

URL = "https://www.inberlinwohnen.de/mein-bereich/wohnungsfinder?q=eyJpdiI6IjQxMWFqaVpaTVNWZE94M2ZYN3lDTmc9PSIsInZhbHVlIjoicVdyZmNsZGd1OVg5MDVKQ2ZLL1lScGV2ZmhCSUMwdTYwdjlYT3MvMDFqL0taMDNQMEF4bitUSGZZMTNheUFRNDIxQnRFYXJmcm13L3FqRUlVcEtyYjJPSHl1TUkxck9mak1OdHRFdE0wS3pKMDRDay9PS0hvVE5LRnBtaXpwb0JKaldhOWFkUmRtS2oxY1kxVCsxUDNGZDU0bkNwajh4NjA5Nk8vZHpkdnBqOHlHSnE0dzQ0RFNuK2N0Mk14U0tOVThVY1ltU2hrSExZaDBvNzFtMG83MUNmL0lGVVZoWVc0V1cyNWdpeVJDdmdCOVVFaUwrOHBGVHZCeWlMUUhpaFdiK3ByTEJObk9ncVNnK29wbzQwYzFNTkEwR2ZZNXpReVZsR2k1akhPbDM0aWFxcDVpZm5nRnVXWVdkb3d3R014RHdrWFdVZi9YV2ZGSlBmd1ZrOXl4bEN6WHZNRGNGSFN2akliVG90YXYvNkErdVNCS2lmS1l6VE9SU0JEZ1owTDFSQ1ZLVVdKVWdBMmhBdlJoZGVMZlRYUkl5UmwrSFdkUHUvYnVONFA5eC9LVG1kKy8welQ2OUx2MURaYlIyMll4Y1BRRW9HbHN5Z3g0WjBsUDhmcUFFM0Q0aHlFeVZjTTBNWVRkR1czZEU9IiwibWFjIjoiN2M1MTQ0YzZjMjliOThkYzc1OTFhOTIyZDBhYTVhNDMyMWU2Y2Q0NDQ2OTRhZTE2NGUzYjM1NWY4NjEyZDU0YiIsInRhZyI6IiJ9"

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
SEEN_FILE = "seen_ids.json"

def load_seen():
    if os.path.exists(SEEN_FILE):
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()

def save_seen(ids):
    with open(SEEN_FILE, "w") as f:
        json.dump(list(ids), f)

def send_telegram(msg):
    requests.post(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"}
    )

def fetch_listings():
    r = requests.get(
        URL,
        cookies={"inberlinwohnen_session": COOKIE},
        headers=HEADERS,
        timeout=30
    )
    soup = BeautifulSoup(r.text, "html.parser")
    listings = []

    for card in soup.select("div[id^='apartment-']"):
        apt_id = card.get("id", "")
        text = card.get_text(" ", strip=True)
        link = card.find("a", href=True)
        href = link["href"] if link else ""
        wbs = "wbs" in text.lower()

        listings.append({
            "id": apt_id,
            "text": text[:300],
            "url": href,
            "wbs": wbs
        })

    return listings

def main():
    seen = load_seen()
    send_telegram("🤖 Wohnung-Bot gestartet! Suche läuft...")
    print("Bot started.")

    while True:
        try:
            listings = fetch_listings()
            print(f"Found {len(listings)} listings")

            for apt in listings:
                if apt["id"] not in seen:
                    seen.add(apt["id"])
                    if not apt["wbs"]:
                        url = apt["url"]
                        if url.startswith("/"):
                            url = "https://www.inberlinwohnen.de" + url
                        send_telegram(
                            f"🏠 <b>Neue Wohnung!</b>\n\n"
                            f"{apt['text']}\n\n"
                            f"🔗 {url}"
                        )
                        print(f"New listing notified: {apt['id']}")

            save_seen(seen)

        except Exception as e:
            print(f"Error: {e}")

        time.sleep(300)

if __name__ == "__main__":
    main()
