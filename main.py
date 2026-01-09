import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
from datetime import datetime

# ==================================================
# CONFIG
# ==================================================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 35

BOT_TOKEN = os.environ.get("BOT_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

DATA_FILE = "data.json"
STATE_FILE = "state.json"

PORT = int(os.environ.get("PORT", 10000))

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

# ==================================================
# LOGGING (HUMAN-READABLE)
# ==================================================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ==================================================
# TELEGRAM
# ==================================================
def send_telegram(text):
    log("📲 Підготовка до відправки повідомлення в Telegram.")
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
        log(f"📲 Telegram відповів статусом {r.status_code}.")
        if r.text:
            log(f"📲 Відповідь Telegram: {r.text}")
    except Exception as e:
        log(f"❌ Помилка Telegram: {e}")

def format_telegram_message(name, old_price, new_price, qty, type_msg):
    return (
        f"<code>{name}</code>\n"
        f"{type_msg} ціни: {old_price} → {new_price}\n"
        f"Кількість: {qty}"
    )

# ==================================================
# PRICE ROUND (ORIGINAL LOGIC)
# ==================================================
def round_price(p):
    if p < 0.009:
        return None
    p_times_1000 = int(round(p * 1000))
    last_digit = p_times_1000 % 10
    base = (p_times_1000 // 10) * 10
    if last_digit >= 9:
        base += 10
    return base / 1000.0

# ==================================================
# PARSER WITH PROXY FALLBACK
# ==================================================
def parse_page():
    log("🔍 Починаю парсинг сайту з цінами.")
    last_error = None

    for idx, proxy in enumerate(PROXY_LIST, start=1):
        log(f"🌍 [{idx}/{len(PROXY_LIST)}] Пробую проксі: {proxy.split('@')[0]}")

        try:
            r = requests.get(
                URL,
                timeout=20,
                proxies={"http": proxy, "https": proxy},
                headers={"User-Agent": "Mozilla/5.0"}
            )

            log(f"🌐 HTTP статус: {r.status_code}")

            if r.status_code != 200:
                last_error = f"HTTP {r.status_code}"
                log("⚠️ Статус не 200 — пробую наступний проксі.")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            items = {}

            tables = soup.find_all("table")
            log(f"📄 Знайдено таблиць: {len(tables)}.")

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

            log(
                f"✅ Парсинг успішний через проксі #{idx}. "
                f"Пропаршено предметів: {len(items)}."
            )
            return items

        except Exception as e:
            last_error = str(e)
            log(f"❌ Проксі #{idx} не підійшов: {e}")

    raise Exception(f"❌ ЖОДЕН ПРОКСІ НЕ СПРАЦЮВАВ. Остання помилка: {last_error}")

# ==================================================
# STATE LOAD / SAVE
# ==================================================
def load_json(path):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ==================================================
# MAIN LOOP (ORIGINAL LOGIC)
# ==================================================
def check_loop():
    log("🧵 Фоновий потік перевірки цін запущено.")

    state = load_json(STATE_FILE)
    if state:
        log("ℹ️ Завантажено існуючі baseline значення.")
    else:
        log("ℹ️ Baseline відсутній — буде створено при першому проході.")

    while True:
        log("🔁 Починаю новий цикл перевірки.")

        try:
            current = parse_page()
        except Exception as e:
            log(f"❌ Парсинг повністю провалився: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        for name, item in current.items():
            price_real = item["price_real"]
            qty = item["qty"]

            price_rounded = round_price(price_real)
            if price_rounded is None:
                log(f"ℹ️ {name}: ціна надто мала — пропущено.")
                continue

            if name not in state:
                state[name] = {"baseline": price_rounded}
                log(f"🆕 {name}: перше виявлення. Baseline = {price_rounded}")
                continue

            baseline = state[name]["baseline"]
            change_percent = ((price_rounded - baseline) / baseline) * 100
            abs_diff = price_rounded - baseline

            if abs(change_percent) >= 30 and abs(abs_diff) >= 0.008:
                msg_type = "Підвищення" if change_percent > 0 else "Падіння"
                log(
                    f"🚨 {name}: значна зміна "
                    f"({baseline} → {price_rounded}, {change_percent:.2f}%)."
                )
                send_telegram(
                    format_telegram_message(
                        name, baseline, price_rounded, qty, msg_type
                    )
                )
                state[name]["baseline"] = price_rounded
                log(f"✅ Baseline для {name} оновлено.")
            else:
                log(
                    f"ℹ️ {name}: зміна {change_percent:.2f}% "
                    f"не відповідає умовам — ігнорується."
                )

        save_json(DATA_FILE, current)
        save_json(STATE_FILE, state)
        log("💾 data.json та state.json оновлено.")

        log(f"⏳ Очікую {CHECK_INTERVAL} секунд до наступної перевірки.")
        time.sleep(CHECK_INTERVAL)

# ==================================================
# FLASK WEB (TABLE VIEW)
# ==================================================
app = Flask(__name__)

def build_html_table():
    if not os.path.exists(DATA_FILE):
        return "<h2>Дані ще не зібрані</h2>"

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    rows = []
    for name, item in sorted(data.items()):
        rows.append(
            f"<tr><td>{name}</td><td>{item['price_real']}</td><td>{item['qty']}</td></tr>"
        )

    return f"""
    <h2>Останні пропарсені дані</h2>
    <table border="1" cellpadding="6" cellspacing="0">
        <tr>
            <th>Назва</th>
            <th>Ціна</th>
            <th>Кількість</th>
        </tr>
        {''.join(rows)}
    </table>
    """

@app.route("/")
def home():
    return """
    <html>
    <head>
        <meta charset="utf-8">
        <title>CSGETTO Parser</title>
        <script>
            async function reloadTable() {
                const r = await fetch('/table');
                document.getElementById('table').innerHTML = await r.text();
            }
            setInterval(reloadTable, 30000);
            window.onload = reloadTable;
        </script>
    </head>
    <body>
        <h1>CSGETTO Price Monitor</h1>
        <div id="table">Завантаження...</div>
    </body>
    </html>
    """

@app.route("/table")
def table():
    return build_html_table()

# ==================================================
# START
# ==================================================
if __name__ == "__main__":
    log("🚀 Сервіс запущено. Ініціалізація компонентів.")
    threading.Thread(target=check_loop, daemon=True).start()
    log("🧵 Фоновий потік перевірки запущено.")

    app.run(host="0.0.0.0", port=PORT)
