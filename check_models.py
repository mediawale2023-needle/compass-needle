import google.generativeai as genai

api_key = "AIzaSyDTs8kUJDwVBhqw93JZDPhdn7aS9L3uc-I"
genai.configure(api_key=api_key)

print("🔍 Checking available models...")
try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ AVAILABLE: {m.name}")
except Exception as e:
    print(f"❌ Error: {e}")