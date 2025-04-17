# bot.py  —  all‐in‐one  (2025‐04‐17)

import time, json, requests, logging, os, csv, glob

from config import TOKEN, OWNER_ID, DATA_DIR

API_URL = f"https://api.telegram.org/bot{TOKEN}/"

offset       = 0
users        = {}        # user_id → state dict
progress     = {}        # user_id → set букв
achievements = {}        # user_id → {'letters':bool,'dict':bool,'rules':bool,'dict_done':set}

# ---------- клавиатура главного меню ----------
MAIN_MENU_BUTTONS = [
    ["🔤 Алфавит", "📜 Правила"],
    ["🏆 Достижения", "📖 Словарь"]
]

def kb(rows):
    return {"keyboard": rows, "resize_keyboard": True}

def tg(method, data=None, retries=3):
    for _ in range(retries):
        try:
            r = requests.post(f"{API_URL}{method}", json=data, timeout=20)
            if r.ok:
                return r.json()
        except Exception as e:
            logging.warning(f"{method} fail: {e}")
        time.sleep(1)

def send(chat_id, text, markup=None):
    tg("sendMessage", {"chat_id": chat_id, "text": text,
                       "parse_mode": "HTML", "reply_markup": markup})

# ---------- приветствие ----------
def handle_start(chat_id):
    caption = (
        "<b>Добро пожаловать в MALKHUT 🧿</b>\n"
        "<i>Mission of Ancient Letters • Knowledge Held Under Truth</i>\n\n"
        "Каждая буква — это не просто знак.\n"
        "Это свет. Смысл. Частица языка, на котором был сотворён мир.\n\n"
        "Здесь ты:\n"
        "🔠 Изучишь ивритский алфавит\n"
        "🧠 Поймёшь глубинные образы\n"
        "✨ Пройдёшь путь от первой буквы до света понимания\n"
        "🏆 Получишь достижения за свой прогресс\n\n"
        "<b>Нажми «Алфавит» в меню — и начни путь.\nЯзык Творения ждёт тебя!</b>"
    )
    try:
        with open("intro.gif", "rb") as f:           # если MP4 → sendVideo
            files = {"animation": f}
            data  = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": json.dumps({
                    "keyboard": MAIN_MENU_BUTTONS,
                    "resize_keyboard": True
                })
            }
            requests.post(f"{API_URL}sendAnimation", data=data, files=files, timeout=20)
    except Exception as e:
        print("Intro send fail:", e)
        send(chat_id, caption, kb(MAIN_MENU_BUTTONS))

# ---------- данные алфавита и правил ----------
with open(os.path.join(DATA_DIR, "alphabet.json"), encoding="utf-8") as f:
    ALPHA = json.load(f)

with open(os.path.join(DATA_DIR, "rules.json"), encoding="utf-8") as f:
    RULES = json.load(f)

# ---------- словари ----------
DICT_DIR   = os.path.join(DATA_DIR, "dictionary")
DICT_EMOJI = {
    "animals": "🦁 Животные",
    "weather": "⛅ Погода",
    "love":    "❤️ Любовь",
    "family":  "👪 Семья",
    "travel":  "✈️ Путешествия"
}
dictionaries = {}
for path in glob.glob(os.path.join(DICT_DIR, "*.csv")):
    cat = os.path.splitext(os.path.basename(path))[0].lower()
    if cat not in DICT_EMOJI:
        continue
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        dictionaries[cat] = [tuple(row[:3]) for row in reader if row]

# ---------- поздравления ----------
def congrats_alpha(chat_id, uid):
    send(chat_id,
         "🎉 <b>Молодец! Ты просмотрел весь алфавит!</b>\n"
         "Теперь буквы ивритского языка — твои друзья, а не загадка.\n"
         "Загляни в «📖 Словарь» и продолжай путешествие!",
         kb([["🏠 Меню"]]))
    achievements.setdefault(uid, {})["letters"] = True

def congrats_rules(chat_id, uid):
    send(chat_id,
         "🎉 <b>Молодец! Ты прочёл все правила!</b>",
         kb([["🏠 Меню"]]))
    achievements.setdefault(uid, {})["rules"] = True

# ---------- алфавит ----------
def show_letter(chat_id, uid):
    idx    = users[uid]["idx"] % len(ALPHA)
    letter = ALPHA[idx]
    text = (
        f"🔤 Буква No{idx+1}: {letter['char']}\n"
        f"📛 Название: {letter['name']}\n"
        f"🔊 Звук: {letter['sound']}\n"
    )
    if "sofit" in letter:
        text += f"✍️ Софит: {letter['sofit']} — {letter['sofit_pron']}\n"
    text += f"📘 Пример: {letter['example']}"

    send(chat_id, text, kb([["◀️ Назад", "Вперёд ▶️"], ["🏠 Меню"]]))

    progress.setdefault(uid, set()).add(letter["char"])
    if len(progress[uid]) == len(ALPHA):
        congrats_alpha(chat_id, uid)

# ---------- правила ----------
def show_rule(chat_id, uid):
    idx  = users[uid]["idx"] % len(RULES)
    rule = RULES[idx]
    send(chat_id,
         f"📜 {rule['title']}\n\n{rule['body']}",
         kb([["◀️ Назад", "Вперёд ▶️"], ["🏠 Меню"]]))
    if idx == len(RULES) - 1:
        congrats_rules(chat_id, uid)

# ---------- достижения ----------
def show_achievements(chat_id, uid):
    a = achievements.get(uid, {})
    lines = [
        "🏆 <b>Достижения</b>\n",
        "🏆 Буквовед"       if a.get("letters") else "🔒 Буквовед — изучи алфавит",
        "🏆 Слововед"       if a.get("dict")    else "🔒 Слововед — пройди все слова",
        "🏆 Мастер иврита"  if a.get("rules")   else "🔒 Мастер иврита — прочти все правила"
    ]
    send(chat_id, "\n".join(lines), kb([["🏠 Меню"]]))

# ---------- словарь: меню категорий и слова ----------
def show_dict_menu(chat_id):
    rows = [[DICT_EMOJI[k]] for k in DICT_EMOJI]
    send(chat_id, "Выбери категорию👇", kb(rows + [["🏠 Меню"]]))

def show_dict_word(chat_id, uid):
    cat   = users[uid]["cat"]
    idx   = users[uid]["idx"]
    words = dictionaries[cat]
    heb, phon, rus = words[idx]
    send(chat_id,
         f"📖 {DICT_EMOJI[cat]}\n"
         f"🔢 Слово {idx+1} / {len(words)}\n\n"
         f"• <b>{heb}</b>\n"
         f"• <i>{phon}</i>\n"
         f"• {rus}",
         kb([["◀️ Назад", "Вперёд ▶️"],
             ["📖 Словарь"],
             ["🏠 Меню"]]))

    # финал категории
    if idx == len(words) - 1:
        send(chat_id,
             "🎉 Ты просмотрел все слова в этой категории!\n"
             "Можешь выбрать другую, пока мы не добавили новые! 😉",
             kb([["📖 Словарь"], ["🏠 Меню"]]))
        # отметка выполнения
        ach = achievements.setdefault(uid, {}).setdefault("dict_done", set())
        ach.add(cat)
        if len(ach) == len(dictionaries):
            achievements[uid]["dict"] = True

# ---------- обработка сообщений ----------
def handle_text(msg):
    uid, chat_id = msg["from"]["id"], msg["chat"]["id"]
    text = msg.get("text", "")

    # старт/меню
    if text == "/start" or text == "🏠 Меню":
        users.pop(uid, None)
        handle_start(chat_id)
        return

    # главное меню
    if text.startswith("🔤"):
        users[uid] = {"mode": "alpha", "idx": 0}
        show_letter(chat_id, uid); return
    if text.startswith("📜"):
        users[uid] = {"mode": "rule",  "idx": 0}
        show_rule(chat_id, uid); return
    if text.startswith("🏆"):
        show_achievements(chat_id, uid); return
    if text.startswith("📖"):
        show_dict_menu(chat_id)
        users[uid] = {"mode": "dict_menu"}; return

    state = users.get(uid)
    if not state:
        return

    # алфавит / правила
    if state["mode"] in ("alpha", "rule"):
        if text.startswith("◀️"):
            state["idx"] -= 1
        elif text.endswith("▶️"):
            state["idx"] += 1
        (show_letter if state["mode"] == "alpha" else show_rule)(chat_id, uid)
        return

    # меню словаря — выбор категории
    if state["mode"] == "dict_menu":
        for key, label in DICT_EMOJI.items():
            if text.startswith(label.split()[0]):
                users[uid] = {"mode": "dict_cat", "cat": key, "idx": 0}
                show_dict_word(chat_id, uid)
                return

    # листание слов
    if state["mode"] == "dict_cat":
        if text.startswith("◀️") and state["idx"] > 0:
            state["idx"] -= 1
        elif text.endswith("▶️") and state["idx"] < len(dictionaries[state["cat"]]) - 1:
            state["idx"] += 1
        elif text.startswith("📖"):
            users[uid] = {"mode": "dict_menu"}
            show_dict_menu(chat_id); return
        show_dict_word(chat_id, uid)

# ---------- основной цикл ----------
while True:
    try:
        upd = tg("getUpdates", {"timeout": 30, "offset": offset})
    except Exception as e:
        print("getUpdates fail:", e); time.sleep(5); continue

    if not upd or "result" not in upd:
        time.sleep(2); continue

    for res in upd["result"]:
        offset = res["update_id"] + 1
        if "message" in res:
            handle_text(res["message"])
