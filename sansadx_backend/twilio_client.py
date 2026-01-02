import os
import requests
from twilio.rest import Client
from requests.auth import HTTPBasicAuth

# ==========================================
# 🔐 TWILIO CREDENTIALS (HARDCODED FOR STABILITY)
# ==========================================
ACCOUNT_SID = "YOUR_ACCOUNT_TOKEN" 
AUTH_TOKEN = "YOUR_AUTH_TOKEN"     
FROM_NUMBER = "whatsapp:+14155238886"  

def send_whatsapp_message(to_number, body_text):
    """
    Sends a WhatsApp message via Twilio.
    """
    print(f"📡 Twilio Client: Attempting to send to {to_number}...")

    try:
        # Check if keys are loaded
        if not ACCOUNT_SID or not AUTH_TOKEN:
            print("❌ Twilio Error: Credentials are empty!")
            return False

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
    """
    Triggers the 'Typing...' animation on the user's WhatsApp.
    """
    # 1. Skip if this is a simulation (no real phone involved)
    if not original_message_sid or "simulate" in original_message_sid:
        return 

    try:
        url = "https://messaging.twilio.com/v2/Indicators/Typing.json"
        
        payload = {
            "MessageSid": original_message_sid,
            "Channel": "whatsapp"
        }
        
        # 2. Manual Request because Twilio Python SDK doesn't support this well yet
        response = requests.post(
            url,
            data=payload,
            auth=HTTPBasicAuth(ACCOUNT_SID, AUTH_TOKEN)
        )
        
        if response.status_code in [200, 201]:
            print(f"⏳ Typing indicator sent for {original_message_sid}")
        else:
            print(f"⚠️ Failed to send typing indicator: {response.text}")
            
    except Exception as e:
        print(f"⚠️ Typing Error: {e}")