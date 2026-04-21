import requests
from bs4 import BeautifulSoup
import json
import time
import os

# ===== تنظیمات =====
TELEGRAM_TOKEN = "TOKEN_BOT_TELEGRAMET"  # از BotFather
CHAT_ID = "CHAT_ID_KHODet"               # از @userinfobot
SESSION_COOKIE = "SESSION_COOKIE_INJAAA" # از قدم ۱

URL = "https://www.inberlinwohnen.de/mein-bereich/wohnungsfinder?q=eyJpdi..."  # لینک کامل خودت

CHECK_INTERVAL = int(os.environ.get("CHECK_INTERVAL", 300))  # 5 دقیقه

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept-Language": "de-DE,de;q=0.9",
}

COOKIES = {
    "inberlinwohnen_session": os.environ.get("SESSION_COOKIE", SESSION_COOKIE),
}

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
    url = f"https://api.telegram.org/bot{os.environ.get('TELEGRAM_TOKEN', TELEGRAM_TOKEN)}/sendMessage"
    requests.post(url, data={
        "chat_id": os.environ.get("CHAT_ID", CHAT_ID),
        "text": msg,
        "parse_mode": "HTML"
    })

def fetch_listings():
    r = requests.get(URL, cookies=COOKIES, headers=HEADERS, timeout=30)
    soup = BeautifulSoup(r.text, "html.parser")
    
    listings = []
    # کارت‌های خونه رو پیدا کن
    cards = soup.select(".wohnungsfinder-result, .apartment-card, article, .listing-item")
    
    for card in cards:
        # ID یا لینک یونیک
        link = card.find("a", href=True)
        title = card.get_text(strip=True)[:100]
        
        wbs = "wbs" in title.lower() or "WBS" in title
        
        href = link["href"] if link else ""
        uid = href or title[:50]
        
        listings.append({
            "id": uid,
            "title": title,
            "url": "https://www.inberlinwohnen.de" + href if href.startswith("/") else href,
            "wbs": wbs
        })
    
    return listings

def main():
    seen = load_seen()
    send_telegram("🤖 Bot gestartet! Suche nach Wohnungen...")
    print("Bot started.")
    
    while True:
        try:
            listings = fetch_listings()
            print(f"Found {len(listings)} listings")
            
            new_count = 0
            for apt in listings:
                if apt["id"] not in seen:
                    if not apt["wbs"]:  # فقط بدون WBS
                        msg = (
                            f"🏠 <b>Neue Wohnung!</b>\n\n"
                            f"{apt['title']}\n\n"
                            f"🔗 {apt['url']}"
                        )
                        send_telegram(msg)
                        new_count += 1
                    seen.add(apt["id"])
            
            save_seen(seen)
            if new_count == 0:
                print("No new listings.")
                
        except Exception as e:
            print(f"Error: {e}")
            send_telegram(f"⚠️ Bot error: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()