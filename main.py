import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
import random
from datetime import datetime

# ===============================
# CONFIG
# ===============================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35

BOT_TOKEN = os.environ.get("8134393467:AAHRcOjVFiy8RTDWSXt3y3u_SDQwYIssK68")
CHAT_ID = os.environ.get("-4840038262")

# Webshare proxies
PROXY_LIST = [
    "http://zlkvzpye-1:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-2:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-3:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-4:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-5:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-6:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-7:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-8:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-9:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-10:lttxslpl8y49@p.webshare.io:80",
]

DATA_FILE = "data.json"
STATE_FILE = "state.json"

# ===============================
# LOGGING
# ===============================
def log(level, msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {level:<5} | {msg}", flush=True)

# ===============================
# TELEGRAM
# ===============================
def send_telegram(text):
    log("INFO", "Sending Telegram message")
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
        log("INFO", f"Telegram status: {r.status_code}")
    except Exception as e:
        log("ERROR", f"Telegram error: {e}")

# ===============================
# PROXY
# ===============================
def get_proxy():
    proxy = random.choice(PROXY_LIST)
    log("INFO", f"Using proxy: {proxy}")
    return {"http": proxy, "https": proxy}

# ===============================
# PRICE ROUND
# ===============================
def round_price(p):
    if p < 0.009:
        return None
    p1000 = int(round(p * 1000))
    base = (p1000 // 10) * 10
    if p1000 % 10 >= 9:
        base += 10
    return base / 1000

# ===============================
# PARSER
# ===============================
def parse_page():
    log("INFO", "Fetching page")
    r = requests.get(
        URL,
        timeout=25,
        proxies=get_proxy(),
        headers={"User-Agent": "Mozilla/5.0"}
    )
    log("INFO", f"HTTP status: {r.status_code}")

    if r.status_code != 200:
        raise Exception(f"Bad HTTP status {r.status_code}")

    soup = BeautifulSoup(r.text, "html.parser")
    items = {}

    for table in soup.find_all("table"):
        for row in table.find_all("tr")[1:]:
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

            if qty < 1 or price < 0.010:
                continue

            items[name] = {"price": price, "qty": qty}

    log("INFO", f"Parsed items: {len(items)}")
    return items

# ===============================
# STATE
# ===============================
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ===============================
# MAIN LOOP
# ===============================
def check_loop():
    log("INFO", "Parser loop started")

    prev_data = load_json(DATA_FILE)
    state = load_json(STATE_FILE)

    while True:
        log("INFO", "New iteration")

        try:
            current = parse_page()
        except Exception as e:
            log("ERROR", f"Parse error: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        for name, item in current.items():
            rounded = round_price(item["price"])
            if rounded is None:
                continue

            if name not in state:
                state[name] = {"baseline": rounded}
                continue

            baseline = state[name]["baseline"]
            diff = rounded - baseline
            percent = diff / baseline * 100

            if abs(percent) >= 30 and abs(diff) >= 0.008:
                msg = (
                    f"<code>{name}</code>\n"
                    f"{'Підвищення' if diff > 0 else 'Падіння'}: "
                    f"{baseline} → {rounded}\n"
                    f"Кількість: {item['qty']}"
                )
                send_telegram(msg)
                log("INFO", f"Alert sent for {name}")
                state[name]["baseline"] = rounded

        save_json(DATA_FILE, current)
        save_json(STATE_FILE, state)

        log("INFO", f"Sleeping {CHECK_INTERVAL}s")
        time.sleep(CHECK_INTERVAL)

# ===============================
# FLASK
# ===============================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running"

# ===============================
# START
# ===============================
if __name__ == "__main__":
    log("INFO", "Starting service")

    try:
        threading.Thread(target=check_loop, daemon=True).start()
        log("INFO", "Background thread started")
    except Exception as e:
        log("ERROR", f"Thread start failed: {e}")

    port = int(os.environ.get("PORT", 5000))
    log("INFO", f"Starting Flask on port {port}")
    app.run(host="0.0.0.0", port=port)
