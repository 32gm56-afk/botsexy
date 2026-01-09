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

last_html_table = "<h2>Немає даних...</h2>"

# ==================================================
# LOGGING
# ==================================================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ==================================================
# TELEGRAM
# ==================================================
def send_telegram(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as e:
        log(f"❌ Telegram error: {e}")

def format_telegram_message(name, old_price, new_price, qty, type_msg):
    return (
        f"<code>{name}</code>\n"
        f"{type_msg} ціни: {old_price} → {new_price}\n"
        f"Кількість: {qty}"
    )

# ==================================================
# PRICE ROUND (ORIGINAL)
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
    last_error = None

    for idx, proxy in enumerate(PROXY_LIST, start=1):
        log(f"🌍 [{idx}/{len(PROXY_LIST)}] Пробую проксі")

        try:
            r = requests.get(
                URL,
                timeout=20,
                proxies={"http": proxy, "https": proxy},
                headers={"User-Agent": "Mozilla/5.0"}
            )

            if r.status_code != 200:
                last_error = f"HTTP {r.status_code}"
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            items = {}

            tables = soup.find_all("table")

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

            log(f"✅ Парсинг успішний. Предметів: {len(items)}")
            return items

        except Exception as e:
            last_error = str(e)
            log(f"❌ Проксі не підійшов: {e}")

    raise Exception(f"❌ Жоден проксі не спрацював: {last_error}")

# ==================================================
# HTML TABLE (ORIGINAL LOGIC)
# ==================================================
def build_html_table(changes):
    if not changes:
        return "<h2>Змін не знайдено.</h2>"

    non_zero = [c for c in changes if float(c["diff"]) != 0]
    zero = [c for c in changes if float(c["diff"]) == 0]

    non_zero.sort(key=lambda x: abs(float(x["diff"])), reverse=True)
    sorted_changes = non_zero + zero

    html = """
    <h2>Зміни за останню перевірку</h2>
    <table border="1" cellspacing="0" cellpadding="6">
        <tr>
            <th>Назва</th>
            <th>Ціна</th>
            <th>Кількість</th>
            <th>Зміна (%)</th>
        </tr>
    """

    for c in sorted_changes:
        html += f"""
        <tr>
            <td>{c['name']}</td>
            <td>{c['price_real']}</td>
            <td>{c['qty']}</td>
            <td>{c['diff']}%</td>
        </tr>
        """

    html += "</table>"
    return html

# ==================================================
# MAIN LOOP (ORIGINAL LOGIC)
# ==================================================
def check_loop():
    global last_html_table

    prev_data = {}
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            prev_data = json.load(f)

    state = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

    while True:
        log("🔁 Починаю новий цикл перевірки")

        try:
            current = parse_page()
        except Exception as e:
            log(f"❌ Парсинг не вдався: {e}")
            time.sleep(CHECK_INTERVAL)
            continue

        changes = []

        for name, item in current.items():
            price_real = item["price_real"]
            qty = item["qty"]

            price_rounded = round_price(price_real)
            if price_rounded is None:
                continue

            if name not in state:
                state[name] = {"baseline": price_rounded}
                continue

            baseline = state[name]["baseline"]
            change_percent = ((price_rounded - baseline) / baseline) * 100
            abs_diff = price_rounded - baseline

            if abs(change_percent) >= 30 and abs(abs_diff) >= 0.008:
                msg_type = "Підвищення" if change_percent > 0 else "Падіння"
                send_telegram(
                    format_telegram_message(
                        name, baseline, price_rounded, qty, msg_type
                    )
                )
                state[name]["baseline"] = price_rounded

            # --- TABLE LOGIC (ORIGINAL) ---
            if name in prev_data:
                old_price = prev_data[name]["price_real"]
                diff_percent = (
                    ((price_real - old_price) / old_price) * 100
                    if old_price > 0 else 0
                )

                changes.append({
                    "name": name,
                    "price_real": price_real,
                    "qty": qty,
                    "diff": f"{diff_percent:.2f}"
                })

        last_html_table = build_html_table(changes)

        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(current, f, indent=2, ensure_ascii=False)

        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)

        prev_data = current
        log("💾 Дані оновлено, очікую наступний цикл")

        time.sleep(CHECK_INTERVAL)

# ==================================================
# FLASK WEB
# ==================================================
app = Flask(__name__)

@app.route("/")
def home():
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>CSGETTO</title>
        <script>
            async function reloadTable() {{
                const r = await fetch('/table');
                document.getElementById('table').innerHTML = await r.text();
            }}
            setInterval(reloadTable, 30000);
            window.onload = reloadTable;
        </script>
    </head>
    <body>
        <div id="table">{last_html_table}</div>
    </body>
    </html>
    """

@app.route("/table")
def table():
    return last_html_table

# ==================================================
# START
# ==================================================
if __name__ == "__main__":
    log("🚀 Сервіс запущено")
    threading.Thread(target=check_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
