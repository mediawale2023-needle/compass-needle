import os
import requests
import json
import re
import logging

logger = logging.getLogger("needle.llm_client")

# ✅ FIX: Load from environment variable, never hardcode
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")


def call_sansadx_model(user_message, system_prompt):
    if not GROQ_API_KEY:
        logger.error("GROQ_API_KEY environment variable is not set.")
        return json.dumps({
            "political_response": "Server Error: GROQ API key not configured.",
            "grievance_data": {"category": "System Error"}
        })

    logger.info("AI Request (Model: llama-3.1-8b-instant)...")
    url = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type": "application/json"
    }

    final_prompt = system_prompt + "\n\nIMPORTANT: Output strictly raw JSON. Do not use Markdown blocks."
    payload = {
        "model": "llama-3.1-8b-instant",
        "messages": [
            {"role": "system", "content": final_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.1
    }

    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload), timeout=30)
        if response.status_code != 200:
            logger.error(f"GROQ ERROR {response.status_code}: {response.text}")
            return json.dumps({
                "political_response": "Server Error: AI temporarily unavailable.",
                "grievance_data": {"category": "System Error"}
            })

        content = response.json()['choices'][0]['message']['content']
        clean_content = re.sub(r"```json\s*|\s*```", "", content).strip()
        return clean_content

    except Exception as e:
        logger.error(f"CRITICAL ERROR in call_sansadx_model: {e}")
        return json.dumps({
            "political_response": "System Error: Check internet connection.",
            "grievance_data": {"category": "Error"}
        })