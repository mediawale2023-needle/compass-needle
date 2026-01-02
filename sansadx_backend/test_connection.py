import requests

# This is exactly what the Dashboard tries to do
url = "http://127.0.0.1:8000/dashboard/summary"
params = {"tenant_id": 1} # We know 'shettar' is Tenant 1

print(f"🔌 Connecting to: {url}...")

try:
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        print("\n✅ CONNECTION SUCCESSFUL!")
        print("------------------------------------------------")
        print(f"📊 RAW DATA FROM BACKEND: {data}")
        print("------------------------------------------------")
        
        # Check if data is empty
        total = data.get("total_active_cases", 0)
        
        # Fallback for old API structure check
        if "total_active_cases" not in data:
             # Check if we are seeing the OLD structure (category_breakdown only)
             cats = data.get("category_breakdown", {})
             total = sum(cats.values())
        
        print(f"🧐 ANALYSIS: The Backend sees {total} grievances.")
        
        if total == 0:
            print("⚠️ PROBLEM: Backend is running, but it is FILTERING out the data.")
            print("👉 FIX: You must restart the backend terminal (Ctrl+C -> uvicorn).")
        else:
            print("🎉 GOOD NEWS: The Backend is sending data!")
            print("👉 FIX: The issue is just your Browser Cache. Refresh the page (Ctrl+R/Cmd+R).")
            
    else:
        print(f"❌ ERROR: Server returned {response.status_code}")
        print(response.text)

except Exception as e:
    print(f"❌ CRITICAL FAILURE: Could not connect to backend.")
    print(f"Reason: {e}")
    print("👉 FIX: Is the backend running? (uvicorn main:app --reload)")