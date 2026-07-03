# -*- coding: utf-8 -*-
from flask import Flask, request
import requests, os, json

app = Flask(__name__)
SETTINGS_FILE = 'settings.json'

# Дефолтные настройки
DEFAULT_SETTINGS = {
    'model': 'deepseek-chat',      # 'deepseek-chat' — старая, но стабильная модель
    'temperature': 1.0,
    'top_p': 1.0,
    'max_tokens': 500
}

def load_settings():
    try:
        with open(SETTINGS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        with open(SETTINGS_FILE, 'w') as f:
            json.dump(DEFAULT_SETTINGS, f)
        return DEFAULT_SETTINGS

def save_settings(settings):
    with open(SETTINGS_FILE, 'w') as f:
        json.dump(settings, f)

@app.route("/")
def index():
    # Страница-заглушка для браузеров ПК
    return '''
    <html>
    <body>
        <p>Сервер работает. WML-интерфейс доступен по адресу:</p>
        <a href="/index.wml">/index.wml</a><br/>
        <a href="/settings.wml">/settings.wml</a>
    </body>
    </html>
    '''

@app.route("/index.wml")
def wml_index():
    with open('index.wml', 'r') as f:
        return f.read(), 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/settings.wml")
def wml_settings():
    settings = load_settings()
    with open('settings.template.wml', 'r') as f:
        template = f.read()
    # Заменяем плейсхолдеры
    wml = template
    wml = wml.replace('{{model_chat_checked}}', 'checked' if settings['model'] == 'deepseek-chat' else '')
    wml = wml.replace('{{model_v4_flash_checked}}', 'checked' if settings['model'] == 'deepseek-v4-flash' else '')
    wml = wml.replace('{{temperature}}', str(settings['temperature']))
    wml = wml.replace('{{top_p}}', str(settings['top_p']))
    wml = wml.replace('{{max_tokens}}', str(settings['max_tokens']))
    return wml, 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/settings", methods=['POST'])
def save_settings_route():
    model = request.form.get('model', 'deepseek-chat')
    temperature = float(request.form.get('temperature', 1.0))
    top_p = float(request.form.get('top_p', 1.0))
    max_tokens = int(request.form.get('max_tokens', 500))
    settings = {
        'model': model,
        'temperature': temperature,
        'top_p': top_p,
        'max_tokens': max_tokens
    }
    save_settings(settings)
    return '''
    <?xml version="1.0"?>
    <!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
    <wml>
      <card id="saved" title="Сохранено">
        <p align="center">
          <b>Настройки сохранены!</b><br/>
          <a href="/index.wml">На главную</a>
        </p>
      </card>
    </wml>
    ''', 200, {'Content-Type': 'text/vnd.wap.wml'}

@app.route("/ask", methods=['POST'])
def ask():
    text = request.form.get("text", "")
    if not text:
        return "Ошибка: нет текста", 400

    DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")
    if not DEEPSEEK_KEY:
        return "Ошибка: API ключ не настроен", 500

    settings = load_settings()
    headers = {
        "Authorization": f"Bearer {DEEPSEEK_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "model": settings['model'],
        "messages": [{"role": "user", "content": text}],
        "max_tokens": settings['max_tokens'],
        "temperature": settings['temperature'],
        "top_p": settings['top_p']
    }

    try:
        resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data, timeout=30)
        if resp.status_code == 200:
            answer = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "Нет ответа")
            # Экранируем для WML
            answer = answer.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
            return f'''
            <?xml version="1.0"?>
            <!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
            <wml>
              <card id="answer" title="Ответ">
                <p align="left">
                  <b>DeepSeek:</b><br/>
                  {answer}
                </p>
                <p>
                  <a href="/index.wml">Новый вопрос</a>
                </p>
              </card>
            </wml>
            ''', 200, {'Content-Type': 'text/vnd.wap.wml'}
        else:
            error_text = f"Ошибка API: {resp.status_code} - {resp.text}"
            return f'''
            <?xml version="1.0"?>
            <!DOCTYPE wml PUBLIC "-//WAPFORUM//DTD WML 1.1//EN" "http://www.wapforum.org/DTD/wml_1.1.xml">
            <wml>
              <card id="error" title="Ошибка">
                <p align="center">
                  <b>Ошибка</b><br/>
                  {error_text}<br/>
                  <a href="/index.wml">Назад</a>
                </p>
              </card>
            </wml>
            ''', 200, {'Content-Type': 'text/vnd.wap.wml'}
    except Exception as e:
        return f"Ошибка сервера: {str(e)}", 500

# Обработчик ошибок для отображения текста вместо HTML-страницы
@app.errorhandler(Exception)
def handle_exception(e):
    return f"Ошибка на сервере: {str(e)}", 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)