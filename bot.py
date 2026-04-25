import requests
import json
import sqlite3
import time
import random
from datetime import datetime

BOT_TOKEN = "token"
ADMIN_ID = 5869616880
REF_LINK = "https://1trade.io/?ref=yZUn2"

API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ================= БД =================
conn = sqlite3.connect("bot.db", check_same_thread=False)
cur = conn.cursor()

def init_db():
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        account_id TEXT,
        reg_approved INTEGER DEFAULT 0,
        deposit_approved INTEGER DEFAULT 0,
        asset TEXT DEFAULT 'EUR/USD OTC',
        expiration TEXT DEFAULT '1 мин',
        signals_today INTEGER DEFAULT 0,
        last_day TEXT
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS deposits (
        user_id INTEGER,
        photo TEXT
    )
    """)
    conn.commit()

def get_user(uid):
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,))
    return cur.fetchone()

def add_user(uid, username):
    cur.execute("INSERT OR IGNORE INTO users(user_id, username) VALUES(?,?)", (uid, username))
    conn.commit()

def update(uid, **kw):
    for k, v in kw.items():
        cur.execute(f"UPDATE users SET {k}=? WHERE user_id=?", (v, uid))
    conn.commit()

def get_users(offset=0):
    cur.execute("SELECT user_id, username FROM users LIMIT 10 OFFSET ?", (offset,))
    return cur.fetchall()

def get_deposits(offset=0):
    cur.execute("SELECT user_id, photo FROM deposits LIMIT 10 OFFSET ?", (offset,))
    return cur.fetchall()

# ================= ДАННЫЕ =================
ASSETS = [
    "EUR/USD OTC","USD/JPY OTC","GBP/USD OTC","USD/CHF OTC",
    "AUD/USD OTC","USD/CAD OTC","EUR/GBP OTC","EUR/JPY OTC",
    "GBP/JPY OTC","AUD/JPY OTC","CHF/JPY OTC","NZD/USD OTC"
]

EXP_MAP = {
    "⚡ 5 сек": "5 сек",
    "⏳ 30 сек": "30 сек",
    "🕐 1 мин": "1 мин",
    "🕒 3 мин": "3 мин"
}

# ================= UI =================
def main_kb():
    return {
        "keyboard": [
            [{"text": "📊 Получить сигнал"}],
            [{"text": "💱 Пара"}, {"text": "⏱ Время"}],
            [{"text": "📈 Статистика"}]
        ],
        "resize_keyboard": True
    }

def assets_kb():
    kb = {"keyboard": [], "resize_keyboard": True}
    for i in range(0, len(ASSETS), 2):
        row = [{"text": ASSETS[i]}]
        if i+1 < len(ASSETS):
            row.append({"text": ASSETS[i+1]})
        kb["keyboard"].append(row)
    return kb

def exp_kb():
    return {
        "keyboard": [
            [{"text": "⚡ 5 сек"}, {"text": "⏳ 30 сек"}],
            [{"text": "🕐 1 мин"}, {"text": "🕒 3 мин"}]
        ],
        "resize_keyboard": True
    }

def admin_kb():
    return {
        "inline_keyboard": [
            [{"text": "👥 ID заявки", "callback_data": "ids_0"}],
            [{"text": "💰 Депозиты", "callback_data": "deps_0"}]
        ]
    }

# ================= ОТПРАВКА =================
def send(chat_id, text, kb=None):
    try:
        data = {"chat_id": chat_id, "text": text}
        if kb:
            data["reply_markup"] = json.dumps(kb)
        requests.post(f"{API}/sendMessage", json=data, timeout=10)
    except Exception as e:
        print(e)

def send_photo(chat_id, photo, caption, kb=None):
    try:
        data = {"chat_id": chat_id, "photo": photo, "caption": caption}
        if kb:
            data["reply_markup"] = json.dumps(kb)
        requests.post(f"{API}/sendPhoto", json=data, timeout=10)
    except Exception as e:
        print(e)

def answer_cb(cb_id):
    try:
        requests.post(f"{API}/answerCallbackQuery", json={"callback_query_id": cb_id})
    except:
        pass

# ================= СИГНАЛ =================
def gen_signal():
    return random.choice(["⬆️ CALL", "⬇️ PUT"])

# ================= ЛОГИКА =================
def handle_message(msg):
    chat_id = msg["chat"]["id"]
    username = msg["from"].get("username","-")
    text = msg.get("text","")
    photo = msg["photo"][-1]["file_id"] if "photo" in msg else None

    add_user(chat_id, username)
    u = get_user(chat_id)

    if text == "/start":
        send(chat_id,
            f"🔥 TRADE BOT\n\n"
            f"📌 Регистрация:\n{REF_LINK}\n\n"
            f"Отправь ID\n\n"
            f"⚠️ Сигналы носят информационный характер.\n"
            f"Результат зависит от рынка."
        )

    elif text == "📊 Получить сигнал":
        if u[4] == 0:
            send(chat_id, "⛔ Доступ ограничен")
            return

        today = datetime.now().strftime("%Y-%m-%d")

        if u[8] != today:
            update(chat_id, signals_today=0, last_day=today)
            u = get_user(chat_id)

        if u[7] >= 30:
            send(chat_id, "⛔ Лимит достигнут")
            return

        direction = gen_signal()
        update(chat_id, signals_today=u[7]+1)

        send(chat_id,
            f"📡 Анализ рынка...\n\n"
            f"📊 Актив: {u[5]}\n"
            f"📉 Возможное движение: {direction}\n"
            f"⏱ Время: {u[6]}\n\n"
            f"📊 Используйте на свой риск\n"
            f"📈 {u[7]+1}/30"
        )

    elif text == "💱 Пара":
        send(chat_id, "Выбери пару 👇", assets_kb())

    elif text in ASSETS:
        update(chat_id, asset=text)
        send(chat_id, f"✅ {text}", main_kb())

    elif text == "⏱ Время":
        send(chat_id, "Выбери время 👇", exp_kb())

    elif text in EXP_MAP:
        update(chat_id, expiration=EXP_MAP[text])
        send(chat_id, f"✅ {EXP_MAP[text]}", main_kb())

    elif text == "📈 Статистика":
        send(chat_id, f"📊 Сегодня: {u[7]}/30")

    elif text == "/admin" and chat_id == ADMIN_ID:
        send(chat_id, "👑 Админка", admin_kb())

    elif text.isdigit():
        update(chat_id, account_id=text)
        send(ADMIN_ID,
            f"👤 @{username}\n🆔 {chat_id}\nID: {text}",
            {"inline_keyboard":[[
                {"text":"✅","callback_data":f"appr_{chat_id}"},
                {"text":"❌","callback_data":f"rej_{chat_id}"}
            ]]}
        )
        send(chat_id, "⏳ Проверка ID")

    elif photo:
        if u[3] == 0:
            send(chat_id, "⚠️ Сначала дождись проверки ID")
            return

        cur.execute("INSERT INTO deposits VALUES (?,?)", (chat_id, photo))
        conn.commit()

        send_photo(ADMIN_ID, photo,
            f"💰 Депозит @{username}\n🆔 {chat_id}",
            {"inline_keyboard":[[
                {"text":"✅","callback_data":f"depok_{chat_id}"},
                {"text":"❌","callback_data":f"deprej_{chat_id}"}
            ]]}
        )

        send(chat_id, "⏳ Проверка депозита")

# ================= CALLBACK =================
def handle_callback(cb):
    data = cb["data"]
    chat_id = cb["from"]["id"]
    answer_cb(cb["id"])

    if chat_id != ADMIN_ID:
        return

    if data.startswith("ids_"):
        page = int(data.split("_")[1])
        users = get_users(page*10)

        kb = [[{"text": f"{u[1]} ({u[0]})", "callback_data": f"user_{u[0]}"}] for u in users]
        kb.append([{"text": "➡️", "callback_data": f"ids_{page+1}"}])

        send(chat_id, "👥 Пользователи", {"inline_keyboard": kb})

    elif data.startswith("appr_"):
        uid = int(data.split("_")[1])
        update(uid, reg_approved=1)
        send(uid, f"💰 Пополни счёт:\n{REF_LINK}")

    elif data.startswith("depok_"):
        uid = int(data.split("_")[1])
        update(uid, deposit_approved=1)
        send(uid, "🎉 Доступ открыт!", main_kb())

# ================= RUN =================
def poll():
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 15})
            data = r.json()

            for upd in data.get("result", []):
                offset = upd["update_id"] + 1

                if "message" in upd:
                    handle_message(upd["message"])

                elif "callback_query" in upd:
                    handle_callback(upd["callback_query"])

        except Exception as e:
            print("ERROR:", e)
            time.sleep(2)

if __name__ == "__main__":
    init_db()
    print("🚀 BOT STARTED")
    poll()
