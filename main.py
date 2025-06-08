from flask import Flask, request, jsonify
import requests
import traceback
import os

app = Flask(__name__)

# === CONFIG ===
WHATSAPP_INSTANCE_ID = os.environ.get("WHATSAPP_INSTANCE_ID")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
FLOWISE_URL = os.environ.get("FLOWISE_URL")
BOT_CHAT_ID = os.environ.get("BOT_ID")  # Пример: "7775885000@c.us"

WHATSAPP_API_URL = f"https://7105.api.greenapi.com/waInstance{WHATSAPP_INSTANCE_ID}/sendMessage/{WHATSAPP_TOKEN}"

# === Flowise Request ===
def ask_flowise(question, history=[]):
    try:
        payload = {
            "question": question,
            "chatHistory": history
        }
        response = requests.post(FLOWISE_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json().get("text", "🤖 Flowise не ответил.")
    except Exception as e:
        print("[ERROR] Flowise call failed:", e)
        return "⚠️ Ошибка при обращении к ИИ. Попробуй позже."

# === WhatsApp Send ===
def send_whatsapp_message(phone, text):
    try:
        payload = {
            "chatId": f"{phone}@c.us",
            "message": text
        }
        response = requests.post(WHATSAPP_API_URL, json=payload)
        print("[SEND]", response.status_code, response.text)
    except Exception:
        print("[ERROR] WhatsApp message failed:")
        traceback.print_exc()

# === Webhook Handler ===
@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    try:
        data = request.get_json(force=True)
        print("[WEBHOOK] Received:", data)

        # === Защита от самогенерации ===
        type_hook = data.get("typeWebhook")
        sender_id = data.get("senderData", {}).get("chatId")
        bot_id = BOT_CHAT_ID

        if type_hook != "incomingMessageReceived":
            return jsonify({"status": "ignored"}), 200

        if sender_id == bot_id:
            print("[SKIP] Self-message detected.")
            return jsonify({"status": "self-message"}), 200

        # === Извлечение текста ===
        message = None
        msg_data = data.get("messageData", {})
        if "textMessageData" in msg_data:
            message = msg_data["textMessageData"].get("textMessage")
        elif "extendedTextMessageData" in msg_data:
            message = msg_data["extendedTextMessageData"].get("text")

        if not message:
            print("[SKIP] Empty or non-text message")
            return jsonify({"status": "no-message"}), 200

        print("[MESSAGE] From:", sender_id, "| Text:", message)
        phone_number = sender_id.replace("@c.us", "")
        answer = ask_flowise(message)
        send_whatsapp_message(phone_number, answer)

        return jsonify({"status": "ok"}), 200

    except Exception:
        traceback.print_exc()
        return jsonify({"status": "fail"}), 500

# === Healthcheck ===
@app.route("/", methods=["GET"])
def root():
    return "Flowise WhatsApp Bot is running ✅"

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
