import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
from datetime import datetime
import random

# ================= CONFIG =================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35

BOT_TOKEN = os.environ.get("8134393467:AAHRcOjVFiy8RTDWSXt3y3u_SDQwYIssK68")
CHAT_ID = os.environ.get("-4840038262")

DATA_FILE = "data.json"
STATE_FILE = "state.json"
LOG_FILE = "changes.log"

PROXY_LIST = [
    "http://zlkvzpye-1:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-2:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-3:lttxslpl8y49@p.webshare.io:80",
]

last_html_table = "<h2>Немає даних...</h2>"

# ================= LOG =================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ================= TELEGRAM =================
def send_telegram(text):
    log("📲 Telegram: sending message")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": CHAT_ID,
                "text": text,
                "parse_mode": "HTML"
            },
            timeout=15
        )
        log(f"📲 Telegram status: {r.status_code}")
    except Exception as e:
        log(f"❌ Telegram error: {e}")

def format_telegram_message(name, old_price, new_price, qty, type_msg):
    return (
        f"<code>{name}</code>\n"
        f"{type_msg} ціни: {old_price} → {new_price}\n"
        f"Кількість: {qty}"
    )

# ================= PRICE ROUND (ORIGINAL) =================
def round_price(p):
    if p < 0.009:
        return None
    p_times_1000 = int(round(p * 1000))
    last_digit = p_times_1000 % 10
    base = (p_times_1000 // 10) * 10
    if last_digit >= 9:
        base += 10
    return base / 1000.0

# ================= PROXY =================
def get_proxy():
    proxy = random.choice(PROXY_LIST)
    log(f"🌍 Using proxy: {proxy}")
    return {"http": proxy, "https": proxy}

# ================= PARSER =================
def parse_page():
    log("🔍 Parsing page")
    r = requests.get(
        URL,
        timeout=25,
        proxies=get_proxy(),
        headers={"User-Agent": "Mozilla/5.0"}
    )
    log(f"🌐 HTTP status: {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")
    items = {}

    tables = soup.find_all("table")
    log(f"📄 Tables found: {len(tables)}")

    for table in tables:
        rows = table.find_all("tr")[1:]
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            name = cols[0].text.strip()
            try:
                price = float(cols[1].text.strip())
            except:
                continue

            max_total = int(cols[3].text.strip())
            max_left = int(cols[4].text.strip())
            qty = max_total - max_left

            if qty < 1 or price < 0.010:
                continue

            items[name] = {"price_real": price, "qty": qty}

    log(f"📊 Parsed items: {len(items)}")
    return items

# ================= STATE =================
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            log(f"⚠ Failed to read {path}")
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================= MAIN LOOP =================
def check_loop():
    log("🧵 Parser loop started")

    prev_data = load_json(DATA_FILE)
    state = load_json(STATE_FILE)

    while True:
        log("🔁 New check iteration")

        try:
            current = parse_page()
        except Exception as e:
            log(f"❌ Parse error: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        for name, item in current.items():
            price_real = item["price_real"]
            qty = item["qty"]

            price_rounded = round_price(price_real)
            if price_rounded is None:
                continue

            if name not in state:
                state[name] = {"baseline": price_rounded}
                log(f"🆕 Baseline set: {name} = {price_rounded}")
                continue

            baseline = state[name]["baseline"]
            change_percent = ((price_rounded - baseline) / baseline) * 100
            abs_diff = price_rounded - baseline

            if abs(change_percent) >= 30 and abs(abs_diff) >= 0.008:
                msg_type = "Підвищення" if change_percent > 0 else "Падіння"
                log(f"🚨 Significant change: {name} {baseline} → {price_rounded}")
                send_telegram(
                    format_telegram_message(
                        name, baseline, price_rounded, qty, msg_type
                    )
                )
                state[name]["baseline"] = price_rounded

        save_json(DATA_FILE, current)
        save_json(STATE_FILE, state)
        log("💾 data.json & state.json updated")

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
    log("🧵 Background parser thread started")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
