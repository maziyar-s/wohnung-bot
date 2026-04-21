import requests
from bs4 import BeautifulSoup
import json
import time
import os

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
                data = json.load(f)
                return set(data)
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
            "parse_mode": "HTML",
        },
        timeout=30,
    )


def safe_text(value):
    if value is None:
        return ""
    return str(value).strip()


def fetch_listings():
    r = requests.get(URL, cookies=COOKIES, headers=HEADERS, timeout=30)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    listings = []

    # همه المان‌هایی که wire:snapshot دارند
    snapshots = soup.find_all(attrs={"wire:snapshot": True})

    seen_snapshot_ids = set()

    for snap in snapshots:
        try:
            raw = snap.get("wire:snapshot", "")
            if not raw or '"item"' not in raw:
                continue

            data = json.loads(raw)
            item = data.get("data", {}).get("item")

            if not item:
                continue

            apartment_id = safe_text(item.get("id"))
            if not apartment_id or apartment_id in seen_snapshot_ids:
                continue

            seen_snapshot_ids.add(apartment_id)

            title = safe_text(item.get("title"))
            street = safe_text(item.get("street"))
            zip_code = safe_text(item.get("zipCode"))
            district = safe_text(item.get("district"))
            rent_net = safe_text(item.get("rentNet"))
            area = safe_text(item.get("area"))
            rooms = safe_text(item.get("rooms"))
            deep_link = safe_text(item.get("deepLink"))

            full_url = deep_link if deep_link else URL

            parts = []
            if rooms:
                parts.append(f"{rooms} Zimmer")
            if area:
                parts.append(f"{area} m²")
            if rent_net:
                parts.append(f"{rent_net} €")

            top_line = " | ".join(parts)

            address_parts = []
            if street:
                address_parts.append(street)
            if zip_code or district:
                address_parts.append(f"{zip_code} {district}".strip())

            address_line = ", ".join([p for p in address_parts if p]).strip(", ")

            full_title_parts = []
            if title:
                full_title_parts.append(title)
            if top_line:
                full_title_parts.append(top_line)
            if address_line:
                full_title_parts.append(address_line)

            final_title = " | ".join(full_title_parts) if full_title_parts else f"Wohnung {apartment_id}"

            wbs_text = f"{title} {street} {district}".lower()
            wbs = "wbs" in wbs_text

            listings.append({
                "id": apartment_id,
                "title": final_title,
                "url": full_url,
                "wbs": wbs,
            })

        except Exception:
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
