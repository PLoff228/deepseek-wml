# -*- coding: utf-8 -*-
from flask import Flask, request
import requests, os

app = Flask(__name__)
DEEPSEEK_KEY = os.environ.get("DEEPSEEK_API_KEY")

@app.route("/")
def index():
    return 'WML gateway for DeepSeek - working'

@app.route("/ask", methods=["POST"])
def ask():
    text = request.form.get("text", "")
    if not text:
        return "Error: no text"
    headers = {"Authorization": f"Bearer {DEEPSEEK_KEY}", "Content-Type": "application/json"}
    data = {"model": "deepseek-chat", "messages": [{"role": "user", "content": text}]}
    resp = requests.post("https://api.deepseek.com/chat/completions", headers=headers, json=data)
    return resp.json().get("choices", [{}])[0].get("message", {}).get("content", "API error")