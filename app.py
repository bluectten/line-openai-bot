from flask import Flask, request, abort
import requests
import os
import logging

# 設定 logging（記錄程式運行時的訊息）
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# 從環境變數讀取金鑰
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

# 用來儲存每個使用者的對話歷史（暫存於記憶體，伺服器重啟會清空）
conversation_history = {}

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

            # 呼叫 OpenAI API，傳入 user_message 和 user_id
            response_text = call_openai_api(user_message, user_id)
            logging.info("OpenAI returned: %s", response_text)

            # 呼叫 LINE Messaging API 並記錄回覆結果
            result = reply_to_line(reply_token, response_text)
            logging.info("LINE reply API response: %s", result)
    return "OK", 200

def call_openai_api(user_message, user_id):
    # 取得該使用者的對話歷史，若無則初始化為空列表
    history = conversation_history.get(user_id, [])
    
    # 如果是首次對話，可加入 system 提示訊息
    if not history:
        history.append({"role": "system", "content": "你是一個友善且樂於助人的助手。"})
    
    # 將最新的使用者訊息加入歷史
    history.append({"role": "user", "content": user_message})
    
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
        # 將機器人的回覆也加入歷史，方便後續對話參考
        history.append({"role": "assistant", "content": reply_text})
        # 更新全域對話歷史
        conversation_history[user_id] = history
        return reply_text
    else:
        return "抱歉，我無法回答你的問題。"

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
    return response.status_code  # 回傳狀態碼，方便檢查是否成功

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
