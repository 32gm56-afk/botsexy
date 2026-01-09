import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
from datetime import datetime

# -------------------------------
# Налаштування
# -------------------------------
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35  # секунд

BOT_TOKEN = os.environ.get("8134393467:AAHRcOjVFiy8RTDWSXt3y3u_SDQwYIssK68")
CHAT_ID   = os.environ.get("-4840038262")

DATA_FILE = "data.json"
STATE_FILE = "state.json"
LOG_FILE = "changes.log"

# 🔌 ПРОКСІ (якщо потрібно)
PROXIES = {
     "http": "http://zlkvzpyе-1:lttxslpl8y49@p.webshare.io:80",
     "https": "http://zlkvzpyе-1:lttxslpl8y49@p.webshare.io:80",
}

last_html_table = "<h2>Немає даних...</h2>"

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

import random

def get_proxy():
    proxy = random.choice(PROXY_LIST)
    return {
        "http": proxy,
        "https": proxy
    }

# -------------------------------
# Telegram
# -------------------------------
def send_telegram(text: str):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    try:
        requests.post(url, json=payload, timeout=15)
    except Exception as e:
        print("Telegram error:", e)

def format_telegram_message(name, old_price, new_price, qty, type_msg):
    return f"<code>{name}</code>\n{type_msg} ціни: {old_price} → {new_price}\nКількість: {qty}"

# -------------------------------
# Логування
# -------------------------------
def log_change(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")

# -------------------------------
# Округлення
# -------------------------------
def round_price(p):
    if p < 0.009:
        return None
    p1000 = int(round(p * 1000))
    base = (p1000 // 10) * 10
    if p1000 % 10 >= 9:
        base += 10
    return base / 1000

# -------------------------------
# Парсер
# -------------------------------
def parse_page():
    r = requests.get(URL, timeout=20, proxies=PROXIES)
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

            items[name] = {"price_real": price, "qty": qty}
    return items

# -------------------------------
# Стан
# -------------------------------
def load_json(path):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            pass
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# -------------------------------
# Основний цикл
# -------------------------------
def check_loop():
    global last_html_table

    prev_data = load_json(DATA_FILE)
    state = load_json(STATE_FILE)

    while True:
        print("🔍 Check...")
        try:
            current = parse_page()
        except Exception as e:
            print("Parse error:", e)
            time.sleep(CHECK_INTERVAL)
            continue

        for name, item in current.items():
            price_r = round_price(item["price_real"])
            if price_r is None:
                continue

            if name not in state:
                state[name] = {"baseline": price_r}

            baseline = state[name]["baseline"]
            diff = price_r - baseline
            percent = (diff / baseline) * 100

            if abs(percent) >= 30 and abs(diff) >= 0.008:
                msg_type = "Підвищення" if diff > 0 else "Падіння"
                send_telegram(format_telegram_message(
                    name, baseline, price_r, item["qty"], msg_type
                ))
                log_change(f"{name}: {baseline} → {price_r} ({percent:.2f}%)")
                state[name]["baseline"] = price_r

        save_json(DATA_FILE, current)
        save_json(STATE_FILE, state)
        time.sleep(CHECK_INTERVAL)

# -------------------------------
# Flask (для Render)
# -------------------------------
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running"

# -------------------------------
# Старт
# -------------------------------
if __name__ == "__main__":
    threading.Thread(target=check_loop, daemon=True).start()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
