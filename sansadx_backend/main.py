from fastapi import FastAPI, Request, Form
import uvicorn
import os
from .twilio_client import send_whatsapp_message, send_typing_indicator
from .ai_engine import ask_groq_agent

app = FastAPI()

@app.get("/")
def home():
    return {"status": "online", "message": "Needle Backend is Running"}

@app.post("/whatsapp/webhook")
async def whatsapp_webhook(request: Request):
    form_data = await request.form()
    
    # 1. Extract Data
    sender = form_data.get("From")
    message_body = form_data.get("Body", "").strip()
    message_sid = form_data.get("MessageSid")

    # 🛑 SAFETY CHECK: Ignore status updates or empty messages
    if not message_body:
        print("ℹ️ Ignoring empty message (likely a status update)")
        return {"status": "ignored"}

    print(f"📩 Message from {sender}: {message_body}")

    # 2. Send 'Typing...' Indicator
    send_typing_indicator(message_sid)

    # 3. Ask the AI
    try:
        # Pass the message to the AI Engine
        ai_reply = ask_groq_agent(message_body)
    except Exception as e:
        print(f"❌ AI Error: {e}")
        ai_reply = "⚠️ Server Error: AI is temporarily unavailable."

    # 4. Reply via Twilio
    send_whatsapp_message(sender, ai_reply)

    return {"status": "replied"}
