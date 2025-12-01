import streamlit as st
import json
import os
from datetime import datetime

ARCHIVE_FILE = "user_archives.json"

def load_archives(username):
    """Loads saved drafts for a specific user."""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r') as f:
            try:
                all_data = json.load(f)
                # Filter for this user
                return [d for d in all_data if d.get('user') == username]
            except:
                return []
    return []

def save_draft(username, title, content, category="General"):
    """Saves a draft to the JSON file."""
    # Load existing data
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r') as f:
            try:
                data = json.load(f)
            except:
                data = []
    else:
        data = []
    
    new_entry = {
        "id": int(datetime.now().timestamp()),
        "user": username,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "category": category,
        "title": title,
        "content": content
    }
    
    data.append(new_entry)
    
    with open(ARCHIVE_FILE, 'w') as f:
        json.dump(data, f, indent=4)
    
    st.toast(f"Saved to Archives: {title}", icon="💾")

def delete_draft(draft_id):
    """Deletes a draft by ID."""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r') as f:
            data = json.load(f)
            
        data = [d for d in data if d['id'] != draft_id]
        
        with open(ARCHIVE_FILE, 'w') as f:
            json.dump(data, f, indent=4)
        st.rerun()