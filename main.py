from flask import Flask, request, jsonify
import requests
import traceback
import os

app = Flask(__name__)

# === CONFIG из .env ===
WHATSAPP_INSTANCE_ID = os.environ.get("WHATSAPP_INSTANCE_ID")
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN")
WHATSAPP_API_URL = f"https://7105.api.greenapi.com/waInstance{WHATSAPP_INSTANCE_ID}/sendMessage/{WHATSAPP_TOKEN}"
FLOWISE_URL = os.environ.get("FLOWISE_URL")

# === Flowise Request ===
def ask_flowise(question, history=[]):
    try:
        payload = {
            "question": question,
            "chatHistory": history
        }
        print("[PAYLOAD TO FLOWISE]:", payload)
        response = requests.post(FLOWISE_URL, json=payload, timeout=120)
        response.raise_for_status()
        return response.json().get("text", "\U0001F916 Flowise не ответил.")
    except Exception as e:
        print("[ERROR] Flowise call failed:", e)
        return "⚠️ Ошибка при обращении к ИИ. Попробуй позже."

# === WhatsApp ===
def send_whatsapp_message(phone, text):
    try:
        payload = {
            "chatId": f"{phone}@c.us",
            "message": text
        }
        requests.post(WHATSAPP_API_URL, json=payload)
    except Exception:
        print("[ERROR] WhatsApp message failed:")
        traceback.print_exc()

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    try:
        data = request.get_json(force=True)
        print("[DEBUG RAW DATA]:", data)

        # 🔪 Критический фильтр, чтобы не отвечать самому себе
        if data.get("typeWebhook") != "incomingMessageReceived":
            print("[INFO] Пропущено: не входящее сообщение.")
            return jsonify({"status": "skipped"}), 200

        message_data = data.get("messageData", {})
        sender = data.get("senderData", {}).get("chatId")

        message = (
            message_data.get("textMessageData", {}).get("textMessage")
            or message_data.get("extendedTextMessageData", {}).get("text")
            or message_data.get("conversationData", {}).get("body")
        )

        print(f"[WhatsApp IN]: {message}")

        if message:
            answer = ask_flowise(message)

            if isinstance(answer, list):
                answer = "\n".join(str(a) for a in answer)
            if len(answer) > 1000:
                answer = answer[:997] + "..."

            if not answer or WHATSAPP_INSTANCE_ID in answer or answer.lower().count("tsunami") > 4:
                print("[WARNING] Подозрительный ответ. Пропущено.")
            else:
                phone_number = sender.replace("@c.us", "")
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
