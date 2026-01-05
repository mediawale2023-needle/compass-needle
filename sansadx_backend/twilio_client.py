import os
import requests
from twilio.rest import Client
from requests.auth import HTTPBasicAuth

# ==========================================
# 🔓 EMERGENCY MODE: HARDCODED CREDENTIALS
# ==========================================
# We are bypassing Railway Variables because the dashboard is stuck.
ACCOUNT_SID = "AC6ce4ae5b2ad4a230e0b65d56da3b1610"
AUTH_TOKEN = "b5e00ab263addd0c062c3acc47f7e93a"
FROM_NUMBER = "whatsapp:+14155238886"

def send_whatsapp_message(to_number, body_text):
    print(f"📡 Twilio Client: Attempting to send to {to_number}...")

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
