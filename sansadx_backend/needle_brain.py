# needle_brain.py

import os
import json
from groq import Groq
from dotenv import load_dotenv

# Load the keys from .env file
load_dotenv()

from prompts import SYSTEM_PROMPT

# Initialize the Groq client
client = Groq(
    api_key=os.environ.get("GROQ_API_KEY"),
)

def analyze_message(user_message, jurisdiction_list):
    """
    Takes a user's WhatsApp message and a list of known areas.
    Returns a Python Dictionary with status, response, and data.
    """
    
    # 1. Format the Jurisdiction List into a string
    jurisdiction_str = "\n- ".join(jurisdiction_list)

    # 2. Inject the context into the System Prompt
    final_prompt = SYSTEM_PROMPT.replace("{JURISDICTION_CONTEXT}", jurisdiction_str)
    final_prompt = final_prompt.replace("{user_message}", user_message)

    try:
        # 3. Call Groq (Llama 3 70B)
        response = client.chat.completions.create(
            # "llama3-70b-8192" is fast and smart enough for this task
            model="llama-3.3-70b-versatile", 
            
            # This forces the model to output valid JSON
            response_format={"type": "json_object"}, 
            
            messages=[
                {"role": "system", "content": final_prompt},
                # We put the user message in the system prompt above, 
                # but you can also add it here as a user role if preferred.
                # For this specific prompt structure, we already injected it.
                 {"role": "user", "content": "Analyze the message above."}
            ],
            temperature=0.1, # Low temp for consistent JSON
        )

        # 4. Parse the JSON
        raw_content = response.choices[0].message.content
        data = json.loads(raw_content)
        return data

    except Exception as e:
        print(f"Error in Needle Brain: {e}")
        return {
            "status": "ERROR",
            "political_response": "Sorry, I am facing a technical issue. Please try again later.",
            "grievance_data": {}
        }

# ==========================================
# QUICK TEST
# ==========================================
if __name__ == "__main__":
    test_areas = ["Tilakwadi", "Shahapur", "Vadgaon"]
    msg = "Please fix the street light in Tilakwadi."
    
    print(f"Testing with message: '{msg}'")
    result = analyze_message(msg, test_areas)
    
    print("\n--- GROQ RESULT ---")
    print(json.dumps(result, indent=2))