import requests
from bs4 import BeautifulSoup
import json
import time
from flask import Flask
import threading
import os
from datetime import datetime

# ================= CONFIG =================
URL = "https://price.csgetto.love/"
CHECK_INTERVAL = 25

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

# ================= LOG =================
def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

# ================= TELEGRAM =================
def send_telegram(text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=15
        )
    except Exception as e:
        log(f"Telegram error: {e}")

# ================= ROUND =================
def round_price(p):
    if p < 0.009:
        return None
    p1000 = int(round(p * 1000))
    base = (p1000 // 10) * 10
    if p1000 % 10 >= 9:
        base += 10
    return base / 1000

# ================= PARSER =================
def parse_page():
    for proxy in PROXY_LIST:
        try:
            r = requests.get(
                URL,
                timeout=20,
                proxies={"http": proxy, "https": proxy},
                headers={"User-Agent": "Mozilla/5.0"}
            )
            if r.status_code != 200:
                continue

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
        except:
            continue

    raise Exception("Жоден проксі не спрацював")

# ================= TABLE =================
def build_html_table(changes):
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

# ================= MAIN LOOP =================
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
        current = parse_page()
        changes = []

        for name, item in current.items():
            price_real = item["price_real"]
            qty = item["qty"]

            # ---------- BASELINE / TELEGRAM ----------
            rounded = round_price(price_real)
            if rounded is not None:
                if name not in state:
                    state[name] = {"baseline": rounded}
                else:
                    baseline = state[name]["baseline"]
                    diff = rounded - baseline
                    change_percent = (diff / baseline) * 100

                    if change_percent >= 25 or change_percent <= -50:
                        send_telegram(
                            f"<code>{name}</code>\n"
                            f"Ціна: {baseline} → {rounded}\n"
                            f"Зміна: {change_percent:.2f}%\n"
                            f"К-сть: {qty}"
                        )
                        state[name]["baseline"] = rounded

            # ---------- TABLE ----------
            if name in prev_data:
                old_price = prev_data[name]["price_real"]
                diff_percent = (
                    ((price_real - old_price) / old_price) * 100
                    if old_price > 0 else 0
                )
            else:
                diff_percent = 0.0

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
        time.sleep(CHECK_INTERVAL)

# ================= FLASK =================
app = Flask(__name__)

@app.route("/")
def home():
    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <script>
            async function reload() {{
                const r = await fetch('/table');
                document.getElementById('t').innerHTML = await r.text();
            }}
            setInterval(reload, 30000);
            window.onload = reload;
        </script>
    </head>
    <body>
        <div id="t">{last_html_table}</div>
    </body>
    </html>
    """

@app.route("/table")
def table():
    return last_html_table

# ================= START =================
if __name__ == "__main__":
    threading.Thread(target=check_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=PORT)
