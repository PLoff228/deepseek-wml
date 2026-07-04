# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, session
import requests, os, json, uuid
from datetime import timedelta

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.permanent_session_lifetime = timedelta(days=30)

DATA_FILE = 'data.json'
ADMIN_LOGIN = "Ploff"
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "default_password")

# ---------- Вспомогательные функции ----------
def load_data():
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "user": {
                "chats": [],
                "global_settings": {
                    "model": "deepseek-v4-flash",
                    "temperature": 1.0,
                    "max_tokens": 500,
                    "system_prompt": "Ты — полезный ассистент. Отвечай на русском языке."
                }
            }
        }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, separators=(',', ':'))

def get_user_data():
    return load_data()["user"]

def save_user_data(user_data):
    d = load_data()
    d["user"] = user_data
    save_data(d)

def get_chat(chat_id):
    user = get_user_data()
    for c in user["chats"]:
        if c["id"] == chat_id:
            return c
    return None

def create_chat(name=None):
    user = get_user_data()
    gs = user["global_settings"]
    num = len(user["chats"]) + 1
    cid = "chat_" + str(uuid.uuid4())[:8]
    new = {
        "id": cid,
        "name": name or f"Чат {num}",
        "messages": [],
        "settings": {
            "model": gs["model"],
            "temperature": gs["temperature"],
            "max_tokens": gs["max_tokens"],
            "system_prompt": gs["system_prompt"]
        }
    }
    user["chats"].insert(0, new)
    save_user_data(user)
    return cid

def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login.wml")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ---------- Роуты ----------
@app.route("/")
def index():
    return '<html><body><a href="/login.wml">WML версия</a></body></html>'

# ----- Вход / выход -----
@app.route("/login.wml", methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        login = request.form.get('login', '')
        password = request.form.get('password', '')
        if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
            session.permanent = True
            session["logged_in"] = True
            session["user"] = login
            return redirect("/index.wml")
        else:
            return '''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="err" title="Ошибка"><p align="center"><b>Неверный логин или пароль</b><br/><a href="/login.wml">Попробовать снова</a></p></card></wml>''', 200, {'Content-Type': 'text/vnd.wap.wml'}
    else:
        return '''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="login" title="Вход"><p align="center"><b>Вход</b><br/>Логин:<br/><input name="login" type="text"/><br/>Пароль:<br/><input name="password" type="text"/><br/><anchor>Войти<go href="/login.wml" method="post"><postfield name="login" value="$(login)"/><postfield name="password" value="$(password)"/></go></anchor></p></card></wml>''', 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login.wml")

# ----- Главная -----
@app.route("/index.wml")
@login_required
def index_wml():
    user = session.get("user", "Гость")
    return f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="main" title="DeepSeek"><p align="center"><b>DeepSeek</b><br/>Привет, {user}!<br/><a href="/new_chat">Создать новый чат</a><br/><a href="/chats.wml">Чаты</a><br/><a href="/settings.wml">Настройки</a><br/><a href="/logout">Выйти</a></p></card></wml>''', 200, {'Content-Type': 'text/vnd.wap.wml'}

# ----- Чаты -----
@app.route("/chats.wml")
@login_required
def chats():
    user = get_user_data()
    chats = user["chats"]
    out = '''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="chats" title="Чаты"><p>'''
    out += '<a href="/new_chat">[Создать новый чат]</a><br/>'
    if not chats:
        out += 'Нет чатов.<br/>'
    else:
        out += f'<a href="/chat.wml?id={chats[0]["id"]}&page=1">Последний чат ({chats[0]["name"]})</a><br/>'
        for c in chats[1:]:
            out += f'<a href="/chat.wml?id={c["id"]}&page=1">{c["name"]}</a><br/>'
    out += '<a href="/index.wml">Главная</a>'
    out += '</p></card></wml>'
    return out, 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/new_chat")
@login_required
def new_chat():
    cid = create_chat()
    return redirect(f'/chat.wml?id={cid}&page=1')

# ----- Чат -----
@app.route("/chat.wml")
@login_required
def chat():
    cid = request.args.get('id')
    page = int(request.args.get('page', 1))
    if not cid:
        return redirect('/chats.wml')
    chat = get_chat(cid)
    if not chat:
        return redirect('/chats.wml')
    
    messages = chat["messages"]
    total = len(messages)
    per_page = 10
    pages = max(1, (total + per_page - 1)//per_page)
    if page < 1: page = 1
    elif page > pages: page = pages
    start = (page - 1) * per_page
    end = min(start + per_page, total)
    page_msgs = messages[start:end]
    
    # Навигация
    nav = ''
    if pages > 1:
        nav += '<p align="center">'
        if page > 1:
            nav += f'<a href="/chat.wml?id={cid}&page=1"><<</a> '
            nav += f'<a href="/chat.wml?id={cid}&page={page-1}"><</a> '
        nav += f'[{page}] '
        if page < pages:
            nav += f'<a href="/chat.wml?id={cid}&page={page+1}">></a> '
            nav += f'<a href="/chat.wml?id={cid}&page={pages}">>></a>'
        nav += '</p>'
    
    # Сообщения
    msg_html = ''
    if not page_msgs:
        msg_html = 'Нет сообщений.'
    else:
        for m in page_msgs:
            role = "User" if m["role"]=="user" else "AI"
            txt = m["content"].replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
            msg_html += f'{role}: {txt}<br/>'
    
    # Форма
    form = f'<input name="message" type="text"/><anchor>Отправить<go href="/chat/send" method="post"><postfield name="chat_id" value="{cid}"/><postfield name="message" value="$(message)"/></go></anchor>'
    
    content = f'{nav}<p>{msg_html}</p><p>{form}</p><p><a href="/chat_settings.wml?id={cid}">[Настройки]</a> <a href="/chats.wml">[Список]</a> <a href="/index.wml">[Главная]</a></p>{nav}'
    
    return f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="chat" title="{chat["name"]}">{content}</card></wml>''', 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/chat/send", methods=['POST'])
@login_required
def send():
    cid = request.form.get('chat_id')
    msg = request.form.get('message', '').strip()
    if not cid or not msg:
        return redirect('/chats.wml')
    chat = get_chat(cid)
    if not chat:
        return redirect('/chats.wml')
    
    chat["messages"].append({"role": "user", "content": msg})
    
    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
    if not DEEPSEEK_KEY:
        chat["messages"].append({"role": "assistant", "content": "API ключ не настроен"})
        save_user_data(get_user_data())
        total = len(chat["messages"])
        return redirect(f'/chat.wml?id={cid}&page={(total+9)//10}')
    
    settings = chat["settings"]
    sys_prompt = settings.get("system_prompt", "Ты — полезный ассистент.")
    
    # Берём последние 20 сообщений + системный промпт
    history = [{"role": "system", "content": sys_prompt}]
    for m in chat["messages"][-20:]:
        history.append(m)
    
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    payload = {
        "model": settings.get("model", "deepseek-v4-flash"),
        "messages": history,
        "max_tokens": settings.get("max_tokens", 500),
        "temperature": settings.get("temperature", 1.0),
        "top_p": 1.0
    }
    try:
        r = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=payload, timeout=15)
        if r.status_code == 200:
            ans = r.json().get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")
        else:
            ans = f"Ошибка API: {r.status_code}"
    except Exception as e:
        ans = f"Ошибка: {str(e)}"
    
    chat["messages"].append({"role": "assistant", "content": ans})
    save_user_data(get_user_data())
    total = len(chat["messages"])
    return redirect(f'/chat.wml?id={cid}&page={(total+9)//10}')

# ----- Настройки чата -----
@app.route("/chat_settings.wml", methods=['GET', 'POST'])
@login_required
def chat_settings():
    if request.method == 'POST':
        cid = request.form.get('chat_id')
        model = request.form.get('model', 'deepseek-v4-flash')
        temp = float(request.form.get('temperature', 1.0))
        max_tok = int(request.form.get('max_tokens', 500))
        sys_prompt = request.form.get('system_prompt', 'Ты — полезный ассистент.')
        chat = get_chat(cid)
        if chat:
            chat["settings"] = {
                "model": model,
                "temperature": temp,
                "max_tokens": max_tok,
                "system_prompt": sys_prompt
            }
            save_user_data(get_user_data())
            return redirect(f'/chat.wml?id={cid}&page=1')
        else:
            return redirect('/chats.wml')
    else:
        cid = request.args.get('id')
        if not cid:
            return redirect('/chats.wml')
        chat = get_chat(cid)
        if not chat:
            return redirect('/chats.wml')
        s = chat["settings"]
        out = f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="chset" title="Настройки чата"><p>
<b>Имя:</b><br/><input name="chat_name" value="{chat["name"]}"/><anchor>Переименовать<go href="/rename_chat" method="post"><postfield name="chat_id" value="{cid}"/><postfield name="new_name" value="$(chat_name)"/></go></anchor><br/>
Модель:<br/><select name="model"><option value="deepseek-v4-flash" {"(selected)" if s["model"]=="deepseek-v4-flash" else ""}>V4 Flash</option><option value="deepseek-v4-pro" {"(selected)" if s["model"]=="deepseek-v4-pro" else ""}>V4 Pro</option></select><br/>
Температура (0-2):<br/><input name="temperature" value="{s["temperature"]}"/><br/>
Макс. токенов:<br/><input name="max_tokens" value="{s["max_tokens"]}"/><br/>
Системный промпт:<br/><input name="system_prompt" value="{s["system_prompt"]}"/><br/>
<anchor>Сохранить<go href="/chat_settings.wml" method="post"><postfield name="chat_id" value="{cid}"/><postfield name="model" value="$(model)"/><postfield name="temperature" value="$(temperature)"/><postfield name="max_tokens" value="$(max_tokens)"/><postfield name="system_prompt" value="$(system_prompt)"/></go></anchor><br/>
<anchor>Удалить чат<go href="/delete_chat" method="post"><postfield name="chat_id" value="{cid}"/></go></anchor><br/>
<a href="/chat.wml?id={cid}&page=1">Назад в чат</a>
</p></card></wml>'''
        return out, 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/rename_chat", methods=['POST'])
@login_required
def rename_chat():
    cid = request.form.get('chat_id')
    new_name = request.form.get('new_name', '').strip()
    if cid and new_name:
        chat = get_chat(cid)
        if chat:
            chat["name"] = new_name
            save_user_data(get_user_data())
    return redirect(f'/chat_settings.wml?id={cid}')

@app.route("/delete_chat", methods=['POST'])
@login_required
def delete_chat():
    cid = request.form.get('chat_id')
    if cid:
        user = get_user_data()
        user["chats"] = [c for c in user["chats"] if c["id"] != cid]
        save_user_data(user)
    return redirect('/chats.wml')

# ----- Глобальные настройки -----
@app.route("/settings.wml", methods=['GET', 'POST'])
@login_required
def settings():
    if request.method == 'POST':
        model = request.form.get('model', 'deepseek-v4-flash')
        temp = float(request.form.get('temperature', 1.0))
        max_tok = int(request.form.get('max_tokens', 500))
        sys_prompt = request.form.get('system_prompt', 'Ты — полезный ассистент.')
        user = get_user_data()
        user["global_settings"] = {
            "model": model,
            "temperature": temp,
            "max_tokens": max_tok,
            "system_prompt": sys_prompt
        }
        save_user_data(user)
        return redirect('/settings.wml')
    else:
        user = get_user_data()
        gs = user["global_settings"]
        out = f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml><card id="settings" title="Настройки"><p>
Модель по умолчанию:<br/><select name="model"><option value="deepseek-v4-flash" {"(selected)" if gs["model"]=="deepseek-v4-flash" else ""}>V4 Flash</option><option value="deepseek-v4-pro" {"(selected)" if gs["model"]=="deepseek-v4-pro" else ""}>V4 Pro</option></select><br/>
Температура (0-2):<br/><input name="temperature" value="{gs["temperature"]}"/><br/>
Макс. токенов:<br/><input name="max_tokens" value="{gs["max_tokens"]}"/><br/>
Системный промпт:<br/><input name="system_prompt" value="{gs["system_prompt"]}"/><br/>
<anchor>Сохранить<go href="/settings.wml" method="post"><postfield name="model" value="$(model)"/><postfield name="temperature" value="$(temperature)"/><postfield name="max_tokens" value="$(max_tokens)"/><postfield name="system_prompt" value="$(system_prompt)"/></go></anchor><br/>
<anchor>Сбросить все данные<go href="/reset_data" method="post"><postfield name="confirm" value="yes"/></go></anchor><br/>
<a href="/index.wml">Главная</a>
</p></card></wml>'''
        return out, 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/reset_data", methods=['POST'])
@login_required
def reset_data():
    if request.form.get('confirm') == 'yes':
        default = {
            "user": {
                "chats": [],
                "global_settings": {
                    "model": "deepseek-v4-flash",
                    "temperature": 1.0,
                    "max_tokens": 500,
                    "system_prompt": "Ты — полезный ассистент. Отвечай на русском языке."
                }
            }
        }
        save_data(default)
    return redirect('/settings.wml')

# ---------- Запуск ----------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)