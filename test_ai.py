import os
import sys
import json
from unittest.mock import patch

# Ensure Python can find the sansadx_backend package
sys.path.append(os.getcwd())

try:
    # 1. Update the import to the new ChatGPT function
    from sansadx_backend.ai_engine import ask_chatgpt_agent
    print("✅ Module Import Successful")
except ImportError as e:
    print(f"❌ Import Failed: {e}")
    sys.exit(1)

# 2. Use env var if set, otherwise mock — NEVER hardcode a real key
_TEST_API_KEY = os.getenv("OPENAI_API_KEY", "test-mock-key-not-for-production")

def run_test():
    # Test case: A message with TWO problems (Road and Water)
    test_message = "Attiwad me road kharab hai aur paani bhi nahi aa raha"
    
    print(f"\n🚀 Testing SansadX Engine v3.0 (OpenAI)...")
    print(f"Input Message: '{test_message}'")
    print("-" * 30)

    try:
        # 3. Call the updated agent
        response = ask_chatgpt_agent(test_message, tenant_id=1)
        
        # 4. Print the full structured response
        print(json.dumps(response, indent=2, ensure_ascii=False))

        # 5. Validation Check for Multi-Label logic
        grievance = response.get("grievance_data", {})
        categories = grievance.get("categories", [])

        print("-" * 30)
        if isinstance(categories, list) and len(categories) > 1:
            print(f"✅ SUCCESS: Multi-label categories detected: {categories}")
        elif isinstance(categories, list):
            print(f"⚠️  PARTIAL: Categories is a list, but only found: {categories}")
        else:
            print("❌ FAIL: Categories is not a list structure.")

    except Exception as e:
        print(f"❌ Test crashed: {e}")

if __name__ == "__main__":
    run_test()