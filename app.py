from flask import Flask, request, abort
import requests
import os
import logging
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# 從環境變數讀取金鑰
LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

@app.route("/webhook", methods=["POST"])
from flask import Flask, request, abort
import requests
import os
import logging

# 設定 logging，這行要放在檔案最上面
logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN", "")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")

@app.route("/webhook", methods=["POST"])
def webhook():
    body = request.get_json()
    logging.info("Received webhook: %s", body)  # 記錄收到的資料
    if not body:
        abort(400)
    events = body.get("events", [])
    for event in events:
        if event.get("type") == "message" and event["message"]["type"] == "text":
            reply_token = event["replyToken"]
            user_message = event["message"]["text"]
            user_id = event["source"].get("userId", "unknown")
            logging.info("User %s sent message: %s", user_id, user_message)

            # 呼叫 OpenAI API 並記錄回應
            response_text = call_openai_api(user_message)
            logging.info("OpenAI returned: %s", response_text)

            # 呼叫 LINE Messaging API 並記錄回覆結果
            result = reply_to_line(reply_token, response_text)
            logging.info("LINE reply API response: %s", result)
    return "OK", 200

def call_openai_api(user_message):
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {OPENAI_API_KEY}"
    }
    data = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": user_message}]
    }
    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
    if response.status_code == 200:
        result = response.json()
        return result["choices"][0]["message"]["content"].strip()
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
    return response.status_code  # 回傳狀態碼，以便知道 LINE API 回覆是否成功

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
