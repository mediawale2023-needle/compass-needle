import requests
import json
import re

# ✅ CORRECT KEY (From your logs)
GROQ_API_KEY = "GROQ_API_KEY"

def call_sansadx_model(user_message, system_prompt):
    print(f"🤖 AI Request (Model: llama-3.1-8b-instant)...")

    url = "https://api.groq.com/openai/v1/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    # Clean prompt setup
    final_prompt = system_prompt + "\n\nIMPORTANT: Output strictly raw JSON. Do not use Markdown blocks."

    payload = {
        "model": "llama-3.1-8b-instant",  # ✅ The Correct New Model
        "messages": [
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        
        if response.status_code != 200:
            print(f"❌ GROQ ERROR {response.status_code}: {response.text}")
            return json.dumps({
                "political_response": "Server Error: AI temporarily unavailable.",
                "grievance_data": {"category": "System Error"}
            })

        # Parse content
        content = response.json()['choices'][0]['message']['content']
        
        # Cleanup any Markdown formatting (```json ... ```)
        clean_content = re.sub(r"```json\s*|\s*```", "", content).strip()
        
        return clean_content

    except Exception as e:
        print(f"❌ CRITICAL ERROR: {e}")
        return json.dumps({
            "political_response": "System Error: Check internet connection.",
            "grievance_data": {"category": "Error"}
        })