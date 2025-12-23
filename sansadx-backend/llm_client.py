from groq import Groq
import json

# ==========================================
# 🛑 FORCE KEY HERE
# ==========================================
MY_KEY = "GROQ_API_KEY" 
# ==========================================

def call_sansadx_model(user_message, system_prompt):
    print(f"DEBUG: Using Key starting with: {MY_KEY[:10]}...")

    try:
        # Direct Initialization
        client = Groq(api_key=MY_KEY)

        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message}
            ],
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            response_format={"type": "json_object"}
        )

        return chat_completion.choices[0].message.content

    except Exception as e:
        print(f"❌ CRITICAL AI ERROR: {e}")
        # Return a fallback JSON so the dashboard doesn't break
        return json.dumps({
            "category": "General",
            "political_response": f"System Error: {str(e)}", 
            "mp_role": "Coordinate"
        })