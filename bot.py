import requests
import os
import time
import json
import re

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
SESSION_COOKIE = os.getenv("SESSION_COOKIE")

URL = "https://www.inberlinwohnen.de/mein-bereich/wohnungsfinder?q=eyJpdiI6Ik9OQTFiU29nMEF0T2VEenVYa09mZ1E9PSIsInZhbHVlIjoiZVZqc0JONUhWU3cwSUpubEtjT2VScjFTUXVPcEpZa1hqMmRPSnlyNmd3UTZWUkR6aTd4UWxlNVMvbG9qWEFkaTZFYXducDA3MFYrV3JveDVYZVRSV3J4elE0VXJkeXNNRk10dCtNVkJlTll0ZElqbWw3aGdaY2VJNTBWR01sY1Z1YS9PUUVacjRnMlR6RUJDay9rczJHekw1elpSVHByNE9ENHFoWVlxSURPWUZJUHpEeEU5UWtJYitJR2NqL1RMd1ZEekptZk10bEVsNnR0enIveElDazlwNlRTUGtnY01La3J2K2hkSnNsVVNCblY3MkYxMmZUVitqR2pmc3I0TWxVVEpJd0d0UjRIWDU4YWl1Y0RxRjhtaHl5WFBxbnRsOS9VaS9hd04rcG91VTVHMWdSNHY0QW5MQks2d0JtSnlHKy9jLzk0UUxRaFZBV3dUM1BUbTlZdmlSY21NQ0RjejEzV2o1Vy9WWWl1VDR5NEdKaUtoZEtZbzd1dXVpMitjWjUrekJRb0sxWm1WMEhlZzVwdkkvWUE5dGtqSnNFMFFUTVJneVRSK3E1eWRJaHlKUGRPc2YwQzNSVGtISStVcTcyTGdNUWF5YkI2Y1B3TDlPdzBGTGJZa2JjMlJIdUllbExhNHorc2lTNlk9IiwibWFjIjoiZWFkMGE3MmQyYzM2OThjNzJkNDhmYTk2ODBjZTljNzNiOWZiNDNmMzJhMDk3YTQ2NjFhMTExMjFlYWUxZTA3YSIsInRhZyI6IiJ9"

CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL", 300))  # هر 5 دقیقه
SEEN_FILE = "seen_ids.json"


def send_telegram(message):
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "HTML"
        },
        timeout=30
    )


def load_seen():
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, "r", encoding="utf-8") as f:
                return set(json.load(f))
        except Exception:
            return set()
    return set()


def save_seen(seen):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)


def get_listings():
    headers = {
        "Cookie": f"inberlinwohnen_session={SESSION_COOKIE}",
        "User-Agent": "Mozilla/5.0",
        "Accept-Language": "de-DE,de;q=0.9"
    }

    r = requests.get(URL, headers=headers, timeout=30)
    html = r.text

    # برای دیباگ اگر لازم شد
    if "wire:snapshot" not in html:
        print("❌ snapshot not found")
        print(html[:2000])
        return []

    matches = re.findall(r'wire:snapshot="([^"]+)"', html)

    listings = []
    seen_ids_local = set()

    for snapshot in matches:
        try:
            snapshot = snapshot.replace("&quot;", '"')
            data = json.loads(snapshot)

            item = data.get("data", {}).get("item")
            if not item:
                continue

            apartment_id = str(item.get("id", "")).strip()
            if not apartment_id or apartment_id in seen_ids_local:
                continue

            seen_ids_local.add(apartment_id)

            rooms = str(item.get("rooms", "")).strip()
            area = str(item.get("area", "")).strip()
            rent = str(item.get("rentNet", "")).strip()
            street = str(item.get("street", "")).strip()
            zipcode = str(item.get("zipCode", "")).strip()
            district = str(item.get("district", "")).strip()
            title = str(item.get("title", "")).strip()
            deeplink = str(item.get("deepLink", "")).strip()

            address = " ".join(x for x in [street, zipcode, district] if x).strip()
            text_parts = []

            if title:
                text_parts.append(title)
            else:
                info = " | ".join(x for x in [f"{rooms} Zimmer" if rooms else "",
                                             f"{area} m²" if area else "",
                                             f"{rent} €" if rent else ""] if x)
                if info:
                    text_parts.append(info)

            if address:
                text_parts.append(address)

            text = " | ".join(text_parts).strip()
            if not text:
                text = f"Wohnung {apartment_id}"

            wbs_text = f"{title} {street} {district}".lower()
            wbs = "wbs" in wbs_text

            listings.append({
                "id": apartment_id,
                "text": text,
                "url": deeplink if deeplink else URL,
                "wbs": wbs
            })

        except Exception as e:
            print("parse error:", e)
            continue

    return listings


def main():
    if not TELEGRAM_TOKEN or not CHAT_ID or not SESSION_COOKIE:
        print("❌ TELEGRAM_TOKEN یا CHAT_ID یا SESSION_COOKIE تنظیم نشده")
        return

    seen = load_seen()

    try:
        send_telegram("🤖 Bot gestartet! Suche nach Wohnungen...")
    except Exception as e:
        print("Telegram start message error:", e)

    print("Bot started...")

    while True:
        try:
            listings = get_listings()
            print(f"Found {len(listings)} listings")

            new_items = 0

            for listing in listings:
                if listing["id"] not in seen:
                    if not listing["wbs"]:
                        msg = (
                            f"🏠 <b>Neue Wohnung!</b>\n\n"
                            f"{listing['text']}\n\n"
                            f"🔗 {listing['url']}"
                        )
                        send_telegram(msg)
                        new_items += 1

                    seen.add(listing["id"])

            save_seen(seen)

            if new_items == 0:
                print("No new listings.")
            else:
                print(f"Sent {new_items} new listing(s).")

        except Exception as e:
            print("Error:", e)
            try:
                send_telegram(f"⚠️ Bot error: {e}")
            except Exception:
                pass

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
