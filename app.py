# -*- coding: utf-8 -*-
from flask import Flask, request, redirect
import requests, os, json, uuid

app = Flask(__name__)

DATA_FILE = 'data.json'

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
    chat_num = len(user["chats"]) + 1
    chat_name = name or f"Чат {chat_num}"
    chat_id = "chat_" + str(uuid.uuid4())[:8]
    new_chat = {
        "id": chat_id,
        "name": chat_name,
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

def render_page(content, title):
    return f'''<?xml version="1.0"?>
<!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
<wml>
  <card id="main" title="{title}">
    {content}
  </card>
</wml>
''', 200, {'Content-Type': 'text/vnd.wap.wml'}

# ---------- Роуты ----------
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

@app.route("/index.wml")
def wml_index():
    content = '''
        <p align="center">
            <b>DeepSeek</b><br/>
            <a href="/new_chat">Создать новый чат</a><br/>
            <a href="/chats.wml">Чаты</a><br/>
            <a href="/settings.wml">Настройки</a>
        </p>
    '''
    return render_page(content, "DeepSeek")

@app.route("/chats.wml")
def wml_chats():
    user = get_user_data()
    chats = user["chats"]
    content = '<p><a href="/new_chat">[Создать новый чат]</a></p>'
    if not chats:
        content += '<p>Нет чатов. Создайте первый!</p>'
    else:
        last = chats[0]
        # URL с &amp; вместо &
        content += f'<p><a href="/chat.wml?id={last["id"]}&amp;page=1">Последний чат ({last["name"]})</a></p>'
        for chat in chats[1:]:
            content += f'<p><a href="/chat.wml?id={chat["id"]}&amp;page=1">{chat["name"]}</a></p>'
    content += '<p><a href="/index.wml">Главная</a></p>'
    return render_page(content, "Чаты")

@app.route("/new_chat")
def new_chat():
    chat_id = create_chat()
    return redirect(f'/chat.wml?id={chat_id}&page=1')

@app.route("/chat.wml")
def wml_chat():
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
    
    # Навигация с &amp;
    nav = ''
    if total_pages > 1:
        nav += '<p align="center">'
        if page > 1:
            nav += f'<a href="/chat.wml?id={chat_id}&amp;page=1"><<</a> '
            nav += f'<a href="/chat.wml?id={chat_id}&amp;page={page-1}"><</a> '
        nav += f'[{page}] '
        if page < total_pages:
            nav += f'<a href="/chat.wml?id={chat_id}&amp;page={page+1}">></a> '
            nav += f'<a href="/chat.wml?id={chat_id}&amp;page={total_pages}">>></a>'
        nav += '</p>'
    
    msg_html = ''
    if not page_msgs:
        msg_html = 'Нет сообщений.'
    else:
        for msg in page_msgs:
            role = "User" if msg["role"] == "user" else "AI"
            text = msg["content"].replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            msg_html += f'{role}: {text}<br/>'
    
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
    return render_page(content, chat['name'])

@app.route("/chat/send", methods=['POST'])
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
        "model": settings.get("model", "deepseek-v4-flash"),
        "messages": messages_for_api,
        "max_tokens": settings.get("max_tokens", 500),
        "temperature": settings.get("temperature", 1.0),
        "top_p": 1.0
    }
    
    try:
        resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=30)
        print(f"API ответ: статус {resp.status_code}, тело: {resp.text}")
        if resp.status_code == 200:
            answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")
        else:
            answer = f"Ошибка API: {resp.status_code} - {resp.text}"
    except Exception as e:
        print(f"Исключение: {e}")
        answer = f"Ошибка сервера: {str(e)}"
    
    chat["messages"].append({"role": "assistant", "content": answer})
    save_user_data(user)
    total = len(chat["messages"])
    last_page = (total + 9) // 10
    return redirect(f'/chat.wml?id={chat_id}&page={last_page}')

@app.route("/chat_settings.wml")
def wml_chat_settings():
    chat_id = request.args.get('id')
    if not chat_id:
        return redirect('/chats.wml')
    chat = get_chat(chat_id)
    if not chat:
        return redirect('/chats.wml')
    
    s = chat["settings"]
    model_flash_selected = 'selected="selected"' if s['model'] == 'deepseek-v4-flash' else ''
    model_pro_selected = 'selected="selected"' if s['model'] == 'deepseek-v4-pro' else ''
    
    content = f'''
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
                <option value="deepseek-v4-flash" {model_flash_selected}>V4 Flash</option>
                <option value="deepseek-v4-pro" {model_pro_selected}>V4 Pro</option>
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
        <p>
            <a href="/chat.wml?id={chat_id}&amp;page=1">Назад в чат</a>
        </p>
    '''
    return render_page(content, "Настройки чата")

@app.route("/chat_settings", methods=['POST'])
def save_chat_settings():
    chat_id = request.form.get('chat_id')
    model = request.form.get('model', 'deepseek-v4-flash')
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
def delete_chat():
    chat_id = request.form.get('chat_id')
    if not chat_id:
        return redirect('/chats.wml')
    user = get_user_data()
    user["chats"] = [c for c in user["chats"] if c["id"] != chat_id]
    save_user_data(user)
    return redirect('/chats.wml')

@app.route("/settings.wml")
def wml_settings():
    user = get_user_data()
    gs = user["global_settings"]
    model_flash_selected = 'selected="selected"' if gs['model'] == 'deepseek-v4-flash' else ''
    model_pro_selected = 'selected="selected"' if gs['model'] == 'deepseek-v4-pro' else ''
    
    content = f'''
        <p>
            Модель по умолчанию:<br/>
            <select name="model">
                <option value="deepseek-v4-flash" {model_flash_selected}>V4 Flash</option>
                <option value="deepseek-v4-pro" {model_pro_selected}>V4 Pro</option>
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
            <a href="/index.wml">Главная</a>
        </p>
    '''
    return render_page(content, "Настройки")

@app.route("/settings", methods=['POST'])
def save_settings():
    model = request.form.get('model', 'deepseek-v4-flash')
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
def reset_data():
    if request.form.get('confirm') == 'yes':
        default_data = {
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
        save_data(default_data)
        return redirect('/index.wml')
    else:
        return redirect('/settings.wml')

@app.errorhandler(Exception)
def handle_exception(e):
    return f"Ошибка на сервере: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
