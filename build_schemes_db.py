import pandas as pd
import glob
import json
import os

def clean_and_build_db():
    print("🚀 Starting Smart Scheme Database Build...")
    master_list = []
    
    # --- PHASE 1: PROCESS EXCEL FILES ---
    excel_files = glob.glob("*.xlsx")
    for xlsx_file in excel_files:
        print(f"📗 Found Excel File: {xlsx_file}")
        try:
            # Read all sheets at once
            all_sheets = pd.read_excel(xlsx_file, sheet_name=None)
            
            for sheet_name, df in all_sheets.items():
                print(f"   👉 Processing Sheet: {sheet_name}")
                process_dataframe(df, sheet_name, master_list)
                
        except Exception as e:
            print(f"   ❌ Error reading Excel file: {e}")

    # --- PHASE 2: PROCESS CSV FILES (Fallback) ---
    csv_files = glob.glob("*.csv")
    # Filter out the main data files we use for other things
    scheme_csvs = [f for f in csv_files if "SCHEMES" in f or "Ministry" in f]
    
    if scheme_csvs:
        print(f"📘 Found {len(scheme_csvs)} CSV files.")
        for csv_file in scheme_csvs:
            try:
                # Guess category from filename (e.g. "SCHEMES - Agriculture.csv")
                clean_name = os.path.basename(csv_file).replace("SCHEMES.xlsx - ", "").replace(".csv", "").strip()
                print(f"   👉 Processing CSV: {clean_name}")
                
                df = pd.read_csv(csv_file)
                process_dataframe(df, clean_name, master_list)
            except Exception as e:
                print(f"   ❌ Error reading CSV: {e}")

    # --- SAVE RESULT ---
    if not master_list:
        print("❌ No schemes found! Please check that 'SCHEMES.xlsx' is in this folder.")
        return

    output_file = "schemes_db.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(master_list, f, indent=4)
        
    print(f"🎉 SUCCESS! Built database with {len(master_list)} schemes.")
    print(f"💾 Saved to: {output_file}")

def process_dataframe(df, category_name, master_list):
    """Helper function to clean and add data from any source (Excel or CSV)"""
    # 1. Clean Column Names
    df.columns = df.columns.str.strip()
    
    # 2. Map variable headers to standard keys
    col_map = {
        "Scheme Name": "name", "Scheme": "name", "Name": "name",
        "Ministry": "ministry", "Department": "ministry",
        "Objective": "description", "Objectives": "description", "Description": "description",
        "Classification": "focus", "Type": "focus", "Focus": "focus",
        "ACTIVE": "active_status", "Active": "active_status", "Status": "active_status"
    }
    df = df.rename(columns=col_map)
    
    # 3. Add to Master List
    for i, row in df.iterrows():
        # Skip empty rows or headers
        if pd.isna(row.get("name")) or row.get("name") == "Scheme Name":
            continue
            
        scheme_obj = {
            "id": f"{category_name}_{i}",
            "name": str(row.get("name", "Unknown")),
            "ministry": str(row.get("ministry", "N/A")),
            "description": str(row.get("description", "No objective provided.")),
            "focus": str(row.get("focus", "General")),
            "category": category_name,  # Sheet Name or Filename becomes Category
            "active": str(row.get("active_status", "Yes"))
        }
        master_list.append(scheme_obj)

if __name__ == "__main__":
    clean_and_build_db()