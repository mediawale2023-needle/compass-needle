import os
import requests
from twilio.rest import Client
from requests.auth import HTTPBasicAuth

# ==========================================
# 🔐 SECURE CREDENTIALS (READS FROM RAILWAY)
# ==========================================
ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")
FROM_NUMBER = os.environ.get("TWILIO_PHONE_NUMBER")

def send_whatsapp_message(to_number, body_text):
    print(f"📡 Twilio Client: Attempting to send to {to_number}...")

    # Validate that keys exist before trying
    if not ACCOUNT_SID or not AUTH_TOKEN:
        print("❌ Twilio Error: Credentials are missing from Railway Variables!")
        print(f"   Debug: SID={ACCOUNT_SID}, Token={'Present' if AUTH_TOKEN else 'Missing'}")
        return False

    try:
        client = Client(ACCOUNT_SID, AUTH_TOKEN)
        message = client.messages.create(
            from_=FROM_NUMBER,
            body=body_text,
            to=to_number
        )
        print(f"✅ Twilio Success! Message SID: {message.sid}")
        return True

    except Exception as e:
        print(f"❌ Twilio Failed: {e}")
        return False

def send_typing_indicator(original_message_sid):
    if not original_message_sid or "simulate" in original_message_sid:
        return 

    try:
        url = "https://messaging.twilio.com/v2/Indicators/Typing.json"
        
        payload = {
            "MessageSid": original_message_sid,
            "Channel": "whatsapp"
        }
        
        response = requests.post(
            url,
            data=payload,
            auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN)
        )
        
        if response.status_code in [200, 201]:
            print(f"⏳ Typing indicator sent.")
        else:
            print(f"⚠️ Failed to send typing indicator: {response.text}")
            
    except Exception as e:
        print(f"⚠️ Typing Error: {e}")
