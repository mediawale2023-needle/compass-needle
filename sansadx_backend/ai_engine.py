import os
import requests
import json

# ==========================================
# 🧠 AI ENGINE (GROQ) - SECURE MODE
# ==========================================

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")

def ask_groq_agent(user_message):
    """
    Sends the user's message to Groq (Llama 3) and returns the reply.
    """
    if not GROQ_API_KEY:
        return "⚠️ Server Error: AI Key is missing in Railway Variables."

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Prompt Engineering: You are an MP's Assistant
    system_prompt = (
        "You are 'Needle', a helpful AI assistant for an Indian Member of Parliament (MP). "
        "Your job is to categorize citizen grievances (Water, Road, Electricity) and reply politely. "
        "Keep replies short (under 50 words) and professional. "
        "If the user reports a problem, say you have noted it for the dashboard."
    )

    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7
    }

    try:
        print(f"🤖 AI Request: Sending '{user_message}' to Groq...")
        response = requests.post(url, headers=headers, json=payload)
        
        if response.status_code == 200:
            data = response.json()
            reply = data["choices"][0]["message"]["content"]
            print("✅ AI Success!")
            return reply
        else:
            print(f"❌ GROQ ERROR {response.status_code}: {response.text}")
            return "⚠️ AI Error: Unable to process request."

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        return "⚠️ Server Error: AI is temporarily unavailable."
