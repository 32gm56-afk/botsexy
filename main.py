import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
from datetime import datetime
import random

# ================== CONFIG ==================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35

BOT_TOKEN = os.environ.get("8134393467:AAHRcOjVFiy8RTDWSXt3y3u_SDQwYIssK68")
CHAT_ID = os.environ.get("-4840038262")

DATA_FILE = "data.json"
STATE_FILE = "state.json"

PROXY_LIST = [
    "http://zlkvzpye-1:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-2:lttxslpl8y49@p.webshare.io:80",
    "http://zlkvzpye-3:lttxslpl8y49@p.webshare.io:80",
]

# ================== LOG ==================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ================== TELEGRAM ==================
def send_telegram(text):
    log("📲 Надсилаю повідомлення в Telegram.")
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
        log(f"✅ Telegram відповів статусом {r.status_code}.")
    except Exception as e:
        log(f"❌ Помилка відправки Telegram: {e}")

# ================== PRICE ROUND (ORIGINAL) ==================
def round_price(p):
    if p < 0.009:
        return None
    p_times_1000 = int(round(p * 1000))
    last_digit = p_times_1000 % 10
    base = (p_times_1000 // 10) * 10
    if last_digit >= 9:
        base += 10
    return base / 1000

# ================== PROXY ==================
def get_proxy():
    proxy = random.choice(PROXY_LIST)
    log(f"🌍 Обрано проксі для запиту: {proxy.split('@')[0]}")
    return {"http": proxy, "https": proxy}

# ================== PARSER ==================
def parse_page():
    log("🔍 Починаю парсинг сторінки з цінами.")
    r = requests.get(
        URL,
        timeout=25,
        proxies=get_proxy(),
        headers={"User-Agent": "Mozilla/5.0"}
    )

    log(f"🌐 Отримано відповідь від сайту (HTTP {r.status_code}).")

    soup = BeautifulSoup(r.text, "html.parser")
    items = {}

    tables = soup.find_all("table")
    log(f"📄 Знайдено {len(tables)} таблиць на сторінці.")

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

            total = int(cols[3].text.strip())
            left = int(cols[4].text.strip())
            qty = total - left

            if qty < 1:
                continue

            items[name] = {"price_real": price, "qty": qty}

    log(f"📊 Успішно пропаршено {len(items)} предметів.")
    return items

# ================== MAIN LOOP ==================
def check_loop():
    log("🧵 Фоновий потік перевірки цін запущено.")

    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        log("ℹ️ Завантажено існуючий state.json (baseline значення).")
    else:
        log("ℹ️ state.json відсутній. Baseline буде створено з нуля.")

    while True:
        log("🔁 Починаю новий цикл перевірки.")

        try:
            current = parse_page()
        except Exception as e:
            log(f"❌ Помилка парсингу: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        for name, item in current.items():
            rounded = round_price(item["price_real"])
            if rounded is None:
                log(f"ℹ️ {name}: ціна надто мала, пропущено.")
                continue

            if name not in state:
                state[name] = {"baseline": rounded}
                log(f"🆕 {name}: перше виявлення. Baseline = {rounded}")
                continue

            baseline = state[name]["baseline"]
            diff = rounded - baseline
            percent = diff / baseline * 100

            if abs(percent) >= 30 and abs(diff) >= 0.008:
                log(f"🚨 {name}: значна зміна ({baseline} → {rounded}, {percent:.2f}%).")
                send_telegram(
                    f"<code>{name}</code>\nЦіна: {baseline} → {rounded}\nК-сть: {item['qty']}"
                )
                state[name]["baseline"] = rounded
                log(f"✅ Baseline для {name} оновлено.")
            else:
                log(f"ℹ️ {name}: зміна {percent:.2f}% — не відповідає умовам.")

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        log("💾 Дані збережено. Очікую наступний цикл.")
        time.sleep(CHECK_INTERVAL)

# ================== FLASK ==================
app = Flask(__name__)

@app.route("/")
def home():
    return "✅ Bot is running"

# ================== START ==================
if __name__ == "__main__":
    log("🚀 Сервіс запущено. Початок ініціалізації.")
    threading.Thread(target=check_loop, daemon=True).start()
    log("🧵 Фоновий потік успішно запущено.")

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
