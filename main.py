import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
import random
from datetime import datetime

# ================= CONFIG =================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35

BOT_TOKEN = os.environ.get("8134393467:AAHRcOjVFiy8RTDWSXt3y3u_SDQwYIssK68")
CHAT_ID = os.environ.get("-4840038262")

PROXY_LIST = [
    "http://zlkvzpye-1:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-2:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-3:lttxslpl8y49@p.webshare.io:80",
]

DATA_FILE = "data.json"

# ================= LOG =================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ================= TELEGRAM =================
def send_telegram(text):
    requests.post(
        f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
        json={"chat_id": CHAT_ID, "text": text},
        timeout=15
    )

# ================= PROXY =================
def get_proxy():
    p = random.choice(PROXY_LIST)
    log(f"🌍 Using proxy: {p}")
    return {"http": p, "https": p}

# ================= PARSER =================
def parse_page():
    log("🔍 Parsing site")
    r = requests.get(
        URL,
        timeout=25,
        proxies=get_proxy(),
        headers={"User-Agent": "Mozilla/5.0"}
    )

    log(f"🌐 HTTP status: {r.status_code}")
    if r.status_code != 200:
        raise Exception("Bad status")

    soup = BeautifulSoup(r.text, "html.parser")
    items = {}

    for row in soup.select("table tr")[1:]:
        cols = row.find_all("td")
        if len(cols) < 5:
            continue

        name = cols[0].text.strip()
        try:
            price = float(cols[1].text.strip())
        except:
            continue

        total = int(cols[3].text.strip())
        left = int(cols[4].text.strip())
        qty = total - left

        if qty < 1:
            continue

        items[name] = {"price": price, "qty": qty}

    log(f"📊 Parsed items: {len(items)}")
    return items

# ================= LOOP =================
def check_loop():
    log("🧵 Parser loop started")

    first_run = not os.path.exists(DATA_FILE)

    while True:
        try:
            current = parse_page()
        except Exception as e:
            log(f"❌ Parse error: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        if first_run:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(current, f, indent=2, ensure_ascii=False)
            log("🆕 First run — baseline saved")
            first_run = False
            time.sleep(CHECK_INTERVAL)
            continue

        with open(DATA_FILE, "r", encoding="utf-8") as f:
            old = json.load(f)

        log("🔁 Comparing prices")

        for name, item in current.items():
            if name not in old:
                continue

            old_price = old[name]["price"]
            new_price = item["price"]

            if new_price != old_price:
                log(f"📉 Change detected: {name} {old_price} → {new_price}")
                send_telegram(
                    f"{name}\nЦіна: {old_price} → {new_price}\nК-сть: {item['qty']}"
                )

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        log("💾 data.json updated")
        time.sleep(CHECK_INTERVAL)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running"

# ================= START =================
if __name__ == "__main__":
    log("🚀 Service started")
    threading.Thread(target=check_loop, daemon=True).start()
    log("🧵 Background parser started")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
