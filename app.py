from flask import Flask, request, abort
import requests
import os
import logging
import sqlite3

# 設定 logging（記錄程式運行時的訊息）
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# 從環境變數讀取金鑰
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 初始化 SQLite 資料庫
def init_db():
    conn = sqlite3.connect("conversations.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

# 儲存對話訊息到資料庫
def save_message(user_id, role, content):
    conn = sqlite3.connect("conversations.db")
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)",
        (user_id, role, content)
    )
    conn.commit()
    conn.close()

# 取得該使用者的對話歷史（依時間排序）
def get_conversation(user_id):
    conn = sqlite3.connect("conversations.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content FROM conversations WHERE user_id = ? ORDER BY timestamp ASC",
        (user_id,)
    )
    rows = cursor.fetchall()
    conn.close()
    messages = []
    for row in rows:
        messages.append({"role": row[0], "content": row[1]})
    return messages

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    logging.info("Received webhook: %s", body)
    if not body:
        abort(400)
    events = body.get("events", [])
    for event in events:
        if event.get("type") == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            user_message = event["message"]["text"]
            user_id = event["source"].get("userId", "unknown")
            logging.info("User %s sent message: %s", user_id, user_message)

            # 儲存使用者的訊息
            save_message(user_id, "user", user_message)

            # 取得該使用者的對話歷史
            history = get_conversation(user_id)
            # 如果沒有系統提示訊息，則在第一筆加上
            if not history or history[0]["role"] != "system":
                history.insert(0, {"role": "system", "content": "你是一個友善且樂於助人的助手。"})

            # 呼叫 OpenAI API 取得回覆
            data = {
                "model": "gpt-3.5-turbo",  # 如需使用 GPT-4，可修改為 "gpt-4"
                "messages": history
            }
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}"
            }
            response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
            if response.status_code == 200:
                result = response.json()
                reply_text = result["choices"][0]["message"]["content"].strip()
                # 儲存機器人的回覆
                save_message(user_id, "assistant", reply_text)
                logging.info("OpenAI returned: %s", reply_text)
                result_status = reply_to_line(reply_token, reply_text)
                logging.info("LINE reply API response: %s", result_status)
            else:
                logging.error("Error calling OpenAI API: %s", response.text)
    return "OK", 200

def reply_to_line(reply_token, text):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }
    data = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }
    response = requests.post("https://api.line.me/v2/bot/message/reply", headers=headers, json=data)
    return response.status_code

if __name__ == "__main__":
    init_db()  # 初始化資料庫與資料表
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
