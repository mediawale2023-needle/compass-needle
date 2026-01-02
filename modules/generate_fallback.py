# Run once: python modules/generate_fallback.py
import requests
import json
import pandas as pd

def generate_fallback():
    db = SchemesDatabase()
    df = db.fetch_all_schemes()
    
    # Export 740 schemes as fallback
    fallback = df.to_dict('records')
    with open('modules/fallback_schemes.json', 'w') as f:
        json.dump(fallback, f, indent=2)
    
    print(f"✅ Generated fallback: {len(fallback)} schemes")

if __name__ == "__main__":
    generate_fallback()
