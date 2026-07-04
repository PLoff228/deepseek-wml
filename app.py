# -*- coding: utf-8 -*-
from flask import Flask, request, redirect, session, url_for
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
                    "model": "deepseek-chat",
                    "temperature": 1.0,
                    "max_tokens": 500,
                    "system_prompt": "Ты — полезный ассистент. Отвечай на русском языке."
                }
            }
        }

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_user_data():
    data = load_data()
    return data["user"]

def save_user_data(user_data):
    data = load_data()
    data["user"] = user_data
    save_data(data)

def get_chat(chat_id):
    user = get_user_data()
    for chat in user["chats"]:
        if chat["id"] == chat_id:
            return chat
    return None

def create_chat(name=None):
    user = get_user_data()
    gs = user["global_settings"]
    chat_id = "chat_" + str(uuid.uuid4())[:8]
    new_chat = {
        "id": chat_id,
        "name": name or "Новый чат",
        "messages": [],
        "settings": {
            "model": gs["model"],
            "temperature": gs["temperature"],
            "max_tokens": gs["max_tokens"],
            "system_prompt": gs["system_prompt"]
        }
    }
    user["chats"].insert(0, new_chat)
    save_user_data(user)
    return chat_id

def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect("/login.wml")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

# ---------- Универсальный рендерер ----------
def render_page(content, title, html_mode=False):
    """Оборачивает контент в WML или HTML в зависимости от html_mode"""
    if html_mode:
        # HTML-версия для отладки на ПК
        return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>{title}</title>
    <style>
        body {{ font-family: sans-serif; max-width: 600px; margin: auto; padding: 10px; background: #f4f4f4; }}
        .card {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
        input, button {{ padding: 8px; margin: 5px 0; width: 100%; box-sizing: border-box; }}
        button {{ background: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }}
        a {{ color: #007bff; text-decoration: none; display: inline-block; margin: 5px 0; }}
        .nav {{ text-align: center; margin: 10px 0; }}
        .nav a {{ margin: 0 5px; }}
        hr {{ margin: 15px 0; }}
    </style>
</head>
<body>
    <div class="card">
        <h2>{title}</h2>
        {content}
    </div>
</body>
</html>
''', 200, {'Content-Type': 'text/html'}
    else:
        # WML-версия для телефона
        return f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml>
  <card id="main" title="{title}">
    {content}
  </card>
</wml>
''', 200, {'Content-Type': 'text/vnd.wap.wml'}

# ---------- Открытые страницы ----------
@app.route("/")
def index():
    return '''
    <html><body>
        <h1>DeepSeek WML</h1>
        <p><a href="/index.wml">Главная (WML)</a></p>
        <p><a href="/chats.wml">Чаты</a></p>
        <p><a href="/settings.wml">Настройки</a></p>
    </body></html>
    '''

@app.route("/login.wml")
def login_page():
    html_mode = 'html' in request.args
    content = '''
        <p align="center">
            <b>Вход в систему</b><br/>
            Логин:<br/>
            <input name="login" type="text" emptyok="false" format="*M"/><br/>
            Пароль:<br/>
            <input name="password" type="text" emptyok="false" format="*M"/><br/>
            <anchor>Войти
                <go href="/login" method="post">
                    <postfield name="login" value="$(login)"/>
                    <postfield name="password" value="$(password)"/>
                </go>
            </anchor>
        </p>
    '''
    # Для HTML-режима преобразуем anchor в форму
    if html_mode:
        content = '''
            <form method="post" action="/login">
                <p>Логин: <input name="login" type="text"/></p>
                <p>Пароль: <input name="password" type="text"/></p>
                <button type="submit">Войти</button>
            </form>
        '''
    return render_page(content, "Вход", html_mode)

@app.route("/login", methods=['POST'])
def login():
    login = request.form.get('login', '')
    password = request.form.get('password', '')
    if login == ADMIN_LOGIN and password == ADMIN_PASSWORD:
        session.permanent = True
        session["logged_in"] = True
        session["user"] = login
        return redirect("/index.wml")
    else:
        html_mode = 'html' in request.args
        content = '''
            <p align="center">
                <b>Неверный логин или пароль</b><br/>
                <a href="/login.wml">Попробовать снова</a>
            </p>
        '''
        return render_page(content, "Ошибка", html_mode)

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login.wml")

# ---------- Защищённые страницы ----------
@app.route("/index.wml")
@login_required
def wml_index():
    html_mode = 'html' in request.args
    user = session.get("user", "Гость")
    content = f'''
        <p align="center">
            <b>DeepSeek</b><br/>
            Привет, {user}!<br/>
            <a href="/new_chat">Новый чат</a><br/>
            <a href="/chats.wml">Чаты</a><br/>
            <a href="/settings.wml">Настройки</a><br/>
            <a href="/logout">Выйти</a>
        </p>
    '''
    return render_page(content, "DeepSeek", html_mode)

@app.route("/chats.wml")
@login_required
def wml_chats():
    html_mode = 'html' in request.args
    user = get_user_data()
    chats = user["chats"]
    content = '<p><a href="/new_chat">[Новый чат]</a></p>'
    if not chats:
        content += '<p>Нет чатов. Создайте первый!</p>'
    else:
        last = chats[0]
        content += f'<p><a href="/chat.wml?id={last["id"]}&page=1">Последний чат ({last["name"]})</a></p>'
        for chat in chats[1:]:
            content += f'<p><a href="/chat.wml?id={chat["id"]}&page=1">{chat["name"]}</a></p>'
    content += '<p><a href="/index.wml">Главная</a></p>'
    return render_page(content, "Чаты", html_mode)

@app.route("/new_chat")
@login_required
def new_chat():
    chat_id = create_chat()
    return redirect(f'/chat.wml?id={chat_id}&page=1')

@app.route("/chat.wml")
@login_required
def wml_chat():
    html_mode = 'html' in request.args
    chat_id = request.args.get('id')
    page = int(request.args.get('page', 1))
    if not chat_id:
        return redirect('/chats.wml')
    chat = get_chat(chat_id)
    if not chat:
        return redirect('/chats.wml')
    
    messages = chat["messages"]
    total_msgs = len(messages)
    per_page = 10
    total_pages = max(1, (total_msgs + per_page - 1) // per_page)
    if page < 1:
        page = 1
    elif page > total_pages:
        page = total_pages
    
    start = (page - 1) * per_page
    end = min(start + per_page, total_msgs)
    page_msgs = messages[start:end]
    
    # Навигация
    nav = ''
    if total_pages > 1:
        nav += '<p align="center">'
        if page > 1:
            nav += f'<a href="/chat.wml?id={chat_id}&page=1"><<</a> '
            nav += f'<a href="/chat.wml?id={chat_id}&page={page-1}"><</a> '
        nav += f'[{page}] '
        if page < total_pages:
            nav += f'<a href="/chat.wml?id={chat_id}&page={page+1}">></a> '
            nav += f'<a href="/chat.wml?id={chat_id}&page={total_pages}">>></a>'
        nav += '</p>'
    
    # Сообщения
    msg_html = ''
    if not page_msgs:
        msg_html = 'Нет сообщений.'
    else:
        for msg in page_msgs:
            role = "User" if msg["role"] == "user" else "AI"
            text = msg["content"].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            msg_html += f'{role}: {text}<br/>'
    
    # Форма отправки (для WML и HTML разная)
    if html_mode:
        form = f'''
            <form method="post" action="/chat/send">
                <input type="hidden" name="chat_id" value="{chat_id}"/>
                <input name="message" type="text" placeholder="Введите сообщение..."/>
                <button type="submit">Отправить</button>
            </form>
        '''
    else:
        form = f'''
            <input name="message" type="text" emptyok="false" format="*M"/>
            <anchor>Отправить
                <go href="/chat/send" method="post">
                    <postfield name="chat_id" value="{chat_id}"/>
                    <postfield name="message" value="$(message)"/>
                </go>
            </anchor>
        '''
    
    content = f'''
        {nav}
        <p>{msg_html}</p>
        <p>{form}</p>
        <p>
            <a href="/chat_settings.wml?id={chat_id}">[Настройки чата]</a>
            <a href="/chats.wml">[Список чатов]</a>
            <a href="/index.wml">[Главная]</a>
        </p>
        {nav}
    '''
    return render_page(content, chat['name'], html_mode)

@app.route("/chat/send", methods=['POST'])
@login_required
def send_message():
    chat_id = request.form.get('chat_id')
    message = request.form.get('message', '').strip()
    if not chat_id or not message:
        return redirect('/chats.wml')
    
    user = get_user_data()
    chat = get_chat(chat_id)
    if not chat:
        return redirect('/chats.wml')
    
    chat["messages"].append({"role": "user", "content": message})
    
    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
    if not DEEPSEEK_KEY:
        chat["messages"].append({"role": "assistant", "content": "Ошибка: API ключ не настроен"})
        save_user_data(user)
        total = len(chat["messages"])
        last_page = (total + 9) // 10
        return redirect(f'/chat.wml?id={chat_id}&page={last_page}')
    
    settings = chat["settings"]
    system_prompt = settings.get("system_prompt", "Ты — полезный ассистент.")
    
    messages_for_api = [{"role": "system", "content": system_prompt}]
    for m in chat["messages"][-20:]:
        messages_for_api.append(m)
    
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": settings.get("model", "deepseek-chat"),
        "messages": messages_for_api,
        "max_tokens": settings.get("max_tokens", 500),
        "temperature": settings.get("temperature", 1.0),
        "top_p": 1.0
    }
    
    try:
        resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")
        else:
            answer = f"Ошибка API: {resp.status_code}"
    except Exception as e:
        answer = f"Ошибка сервера: {str(e)}"
    
    chat["messages"].append({"role": "assistant", "content": answer})
    save_user_data(user)
    total = len(chat["messages"])
    last_page = (total + 9) // 10
    return redirect(f'/chat.wml?id={chat_id}&page={last_page}')

@app.route("/chat_settings.wml")
@login_required
def wml_chat_settings():
    html_mode = 'html' in request.args
    chat_id = request.args.get('id')
    if not chat_id:
        return redirect('/chats.wml')
    chat = get_chat(chat_id)
    if not chat:
        return redirect('/chats.wml')
    
    s = chat["settings"]
    # Для HTML-режима используем форму, для WML — anchor с go
    if html_mode:
        form = f'''
            <form method="post" action="/chat_settings">
                <input type="hidden" name="chat_id" value="{chat_id}"/>
                <p>Имя чата: <input name="chat_name" type="text" value="{chat['name']}"/></p>
                <p>Модель: 
                    <select name="model">
                        <option value="deepseek-chat" {"selected" if s['model']=='deepseek-chat' else ""}>deepseek-chat</option>
                        <option value="deepseek-v4-flash" {"selected" if s['model']=='deepseek-v4-flash' else ""}>deepseek-v4-flash</option>
                    </select>
                </p>
                <p>Температура (0-2): <input name="temperature" type="text" value="{s['temperature']}"/></p>
                <p>Макс. токенов: <input name="max_tokens" type="text" value="{s['max_tokens']}"/></p>
                <p>Системный промпт: <input name="system_prompt" type="text" value="{s['system_prompt']}"/></p>
                <button type="submit">Сохранить настройки</button>
            </form>
            <form method="post" action="/delete_chat" style="margin-top:10px;">
                <input type="hidden" name="chat_id" value="{chat_id}"/>
                <button type="submit" style="background:red;">Удалить чат</button>
            </form>
        '''
    else:
        form = f'''
            <p>
                <b>Имя чата:</b><br/>
                <input name="chat_name" type="text" value="{chat['name']}" format="*M"/>
                <anchor>Переименовать
                    <go href="/rename_chat" method="post">
                        <postfield name="chat_id" value="{chat_id}"/>
                        <postfield name="new_name" value="$(chat_name)"/>
                    </go>
                </anchor>
            </p>
            <p>
                Модель:<br/>
                <select name="model">
                    <option value="deepseek-chat" {"(selected)" if s['model']=='deepseek-chat' else ""}>deepseek-chat</option>
                    <option value="deepseek-v4-flash" {"(selected)" if s['model']=='deepseek-v4-flash' else ""}>deepseek-v4-flash</option>
                </select>
            </p>
            <p>
                Температура (0-2):<br/>
                <input name="temperature" type="text" value="{s['temperature']}" format="*N"/>
            </p>
            <p>
                Макс. токенов:<br/>
                <input name="max_tokens" type="text" value="{s['max_tokens']}" format="*N"/>
            </p>
            <p>
                Системный промпт:<br/>
                <input name="system_prompt" type="text" value="{s['system_prompt']}" format="*M"/>
            </p>
            <p>
                <anchor>Сохранить настройки
                    <go href="/chat_settings" method="post">
                        <postfield name="chat_id" value="{chat_id}"/>
                        <postfield name="model" value="$(model)"/>
                        <postfield name="temperature" value="$(temperature)"/>
                        <postfield name="max_tokens" value="$(max_tokens)"/>
                        <postfield name="system_prompt" value="$(system_prompt)"/>
                    </go>
                </anchor>
            </p>
            <p>
                <anchor>Удалить чат
                    <go href="/delete_chat" method="post">
                        <postfield name="chat_id" value="{chat_id}"/>
                    </go>
                </anchor>
            </p>
        '''
    content = form + f'<p><a href="/chat.wml?id={chat_id}&page=1">Назад в чат</a></p>'
    return render_page(content, "Настройки чата", html_mode)

@app.route("/chat_settings", methods=['POST'])
@login_required
def save_chat_settings():
    chat_id = request.form.get('chat_id')
    model = request.form.get('model', 'deepseek-chat')
    temperature = float(request.form.get('temperature', 1.0))
    max_tokens = int(request.form.get('max_tokens', 500))
    system_prompt = request.form.get('system_prompt', 'Ты — полезный ассистент.')
    
    user = get_user_data()
    chat = get_chat(chat_id)
    if not chat:
        return redirect('/chats.wml')
    
    chat["settings"] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt
    }
    save_user_data(user)
    return redirect(f'/chat.wml?id={chat_id}&page=1')

@app.route("/rename_chat", methods=['POST'])
@login_required
def rename_chat():
    chat_id = request.form.get('chat_id')
    new_name = request.form.get('new_name', '').strip()
    if not chat_id or not new_name:
        return redirect('/chats.wml')
    user = get_user_data()
    chat = get_chat(chat_id)
    if chat:
        chat["name"] = new_name
        save_user_data(user)
    return redirect(f'/chat_settings.wml?id={chat_id}')

@app.route("/delete_chat", methods=['POST'])
@login_required
def delete_chat():
    chat_id = request.form.get('chat_id')
    if not chat_id:
        return redirect('/chats.wml')
    user = get_user_data()
    user["chats"] = [c for c in user["chats"] if c["id"] != chat_id]
    save_user_data(user)
    return redirect('/chats.wml')

@app.route("/settings.wml")
@login_required
def wml_settings():
    html_mode = 'html' in request.args
    user = get_user_data()
    gs = user["global_settings"]
    
    if html_mode:
        content = f'''
            <form method="post" action="/settings">
                <p>Модель по умолчанию:
                    <select name="model">
                        <option value="deepseek-chat" {"selected" if gs['model']=='deepseek-chat' else ""}>deepseek-chat</option>
                        <option value="deepseek-v4-flash" {"selected" if gs['model']=='deepseek-v4-flash' else ""}>deepseek-v4-flash</option>
                    </select>
                </p>
                <p>Температура (0-2): <input name="temperature" type="text" value="{gs['temperature']}"/></p>
                <p>Макс. токенов: <input name="max_tokens" type="text" value="{gs['max_tokens']}"/></p>
                <p>Системный промпт (по умолчанию): <input name="system_prompt" type="text" value="{gs['system_prompt']}"/></p>
                <button type="submit">Сохранить</button>
            </form>
            <form method="post" action="/reset_data" style="margin-top:10px;">
                <input type="hidden" name="confirm" value="yes"/>
                <button type="submit" style="background:orange;">Сбросить все данные</button>
            </form>
        '''
    else:
        content = f'''
            <p>
                Модель по умолчанию:<br/>
                <select name="model">
                    <option value="deepseek-chat" {"(selected)" if gs['model']=='deepseek-chat' else ""}>deepseek-chat</option>
                    <option value="deepseek-v4-flash" {"(selected)" if gs['model']=='deepseek-v4-flash' else ""}>deepseek-v4-flash</option>
                </select>
            </p>
            <p>
                Температура (0-2):<br/>
                <input name="temperature" type="text" value="{gs['temperature']}" format="*N"/>
            </p>
            <p>
                Макс. токенов:<br/>
                <input name="max_tokens" type="text" value="{gs['max_tokens']}" format="*N"/>
            </p>
            <p>
                Системный промпт (по умолчанию):<br/>
                <input name="system_prompt" type="text" value="{gs['system_prompt']}" format="*M"/>
            </p>
            <p>
                <anchor>Сохранить
                    <go href="/settings" method="post">
                        <postfield name="model" value="$(model)"/>
                        <postfield name="temperature" value="$(temperature)"/>
                        <postfield name="max_tokens" value="$(max_tokens)"/>
                        <postfield name="system_prompt" value="$(system_prompt)"/>
                    </go>
                </anchor>
            </p>
            <p>
                <anchor>Сбросить все данные
                    <go href="/reset_data" method="post">
                        <postfield name="confirm" value="yes"/>
                    </go>
                </anchor>
            </p>
        '''
    content += '<p><a href="/index.wml">Главная</a></p>'
    return render_page(content, "Настройки", html_mode)

@app.route("/settings", methods=['POST'])
@login_required
def save_settings():
    model = request.form.get('model', 'deepseek-chat')
    temperature = float(request.form.get('temperature', 1.0))
    max_tokens = int(request.form.get('max_tokens', 500))
    system_prompt = request.form.get('system_prompt', 'Ты — полезный ассистент.')
    
    user = get_user_data()
    user["global_settings"] = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "system_prompt": system_prompt
    }
    save_user_data(user)
    return redirect('/settings.wml')

@app.route("/reset_data", methods=['POST'])
@login_required
def reset_data():
    if request.form.get('confirm') == 'yes':
        default_data = {
            "user": {
                "chats": [],
                "global_settings": {
                    "model": "deepseek-chat",
                    "temperature": 1.0,
                    "max_tokens": 500,
                    "system_prompt": "Ты — полезный ассистент. Отвечай на русском языке."
                }
            }
        }
        save_data(default_data)
        return redirect('/index.wml')
    else:
        return redirect('/settings.wml')

# ---------- Обработчик ошибок ----------
@app.errorhandler(Exception)
def handle_exception(e):
    return f"Ошибка на сервере: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)