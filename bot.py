import requests
from bs4 import BeautifulSoup
import json
import time
import os
import re

# ===== تنظیمات =====
TELEGRAM_TOKEN = ""
CHAT_ID = ""
SESSION_COOKIE = ""

URL = "https://www.inberlinwohnen.de/mein-bereich/wohnungsfinder?q=eyJpdiI6IkZuYnJGa0xCT0liL1d0UFNrbTNUWUE9PSIsInZhbHVlIjoid3g4SWdPOEdmMi9BSDBQVlFOTzJSUEZTWDA3cG12c0UvR3AxcFJoNzk0c1NvMVIySEtJN0tJR2JUTFhnNC9hbjJaQ0pNUHFlaFRoa3k0Z1U5WDFkdDk5anFqbmJVV0dSRENNTFFzeDFRMEl0TkZ5SDZQUzFvYUNIdkNBMEV2VDdvZ3JVMk9IR0ZUYXZndkFUekp1aUM5cHB5QU4vbG8yUnlmNFIycEloOExxRy9Wb1NLLzBVckhzelRqZHdsSHJXeXNRRjRqSU9EUXUvUjdhaDRvd3NYQzF1VnZZdGtGVjRkOG5mZGtlVVI5ME40TThWaVM2VnZCSlhLRjBuUmE2YW04My94VC94allET0FpNmlEdVBrdkFvZnowVTR3SE52UTdpLzVsNDBaM01SRkdFd1pBcTFCOEdyajNNNFZpdnVBdDYrMUgzSElaeXZYNnRxZjh6NkdJZi8raGVTb2NVQnBlbmhqYUlCUlJUcWd4em1VbTdzcVZDelk3QWlweGRJV2RHbFlpOURDUk5wQXVaQ01DSnFsMnBkVkJXVDJRZWxUVThIWmgxa2N0QkJoMXNaQW9aaFlXM2txNTZKNzZnSGtpRmhTZysxRDVFOXM4bkhTbFpsK1QrYVJpT1VRcDQxbFpSQWc0OGg5K1U9IiwibWFjIjoiZmQwYTZhMjIzMTAyNDM5NTZhMWRlMGQ3YTE2NzA5Y2VkNDUyZTkzZjIyM2FhYTE2OGZmYjA0MjAyN2E3NGMwNyIsInRhZyI6IiJ9"

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
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(ids):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(ids), f, ensure_ascii=False, indent=2)


def send_telegram(msg):
    token = os.environ.get("TELEGRAM_TOKEN", TELEGRAM_TOKEN)
    chat_id = os.environ.get("CHAT_ID", CHAT_ID)

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(
        url,
        data={
            "chat_id": chat_id,
            "text": msg,
            "parse_mode": "HTML"
        },
        timeout=30
    )


def clean_text(text):
    return " ".join(text.split()).strip()


def fetch_listings():
    r = requests.get(URL, cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()

    html = r.text
    soup = BeautifulSoup(html, "html.parser")

    listings = []

    # راه اصلی: پیدا کردن div هایی که id آنها با apartment- شروع می‌شود
    apartment_divs = soup.select('div[id^="apartment-"]')

    # اگر چیزی پیدا نشد، برای دیباگ یک تکه از HTML را چاپ کن
    if not apartment_divs:
        print("DEBUG: apartment divs not found")
        print(html[:2000])
        return listings

    for div in apartment_divs:
        try:
            div_id = div.get("id", "").strip()  # مثل apartment-16008
            if not div_id.startswith("apartment-"):
                continue

            apartment_id = div_id.replace("apartment-", "").strip()
            if not apartment_id:
                continue

            # کل متن آگهی
            text = clean_text(div.get_text(" ", strip=True))

            # حذف علامت + آخر سطر اگر بود
            if text.endswith("+"):
                text = text[:-1].strip()

            # پیدا کردن URL از deep link داخل snapshot یا هر href موجود
            url = URL

            # اول سعی می‌کنیم href پیدا کنیم
            a_tag = div.find("a", href=True)
            if a_tag:
                href = a_tag["href"].strip()
                if href.startswith("/"):
                    url = "https://www.inberlinwohnen.de" + href
                elif href.startswith("http"):
                    url = href

            # اگر href نبود، از متن HTML دنبال deepLink بگرد
            if url == URL:
                div_html = str(div)
                m = re.search(r'"deepLink":"(https?:\/\/[^"]+)"', div_html)
                if m:
                    url = m.group(1).replace("\\/", "/")

            wbs = "wbs" in text.lower()

            listings.append({
                "id": apartment_id,
                "title": text,
                "url": url,
                "wbs": wbs
            })

        except Exception as e:
            print(f"DEBUG item parse error: {e}")
            continue

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
                    if not apt["wbs"]:
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
            else:
                print(f"Sent {new_count} new listing(s).")

        except Exception as e:
            print(f"Error: {e}")
            try:
                send_telegram(f"⚠️ Bot error: {e}")
            except Exception:
                pass

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
