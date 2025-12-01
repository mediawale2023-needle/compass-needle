import streamlit as st
import json
import os
from datetime import datetime

# Define the folder where user drafts will be stored
ARCHIVE_DIR = "user_archives"
if not os.path.exists(ARCHIVE_DIR):
    os.makedirs(ARCHIVE_DIR)

def get_user_archive_path(username):
    """Returns the specific file path for a user's archive JSON."""
    return os.path.join(ARCHIVE_DIR, f"{username}_drafts.json")

def save_draft(username, title, content):
    """Saves a generated draft to the user's persistent JSON archive."""
    file_path = get_user_archive_path(username)
    
    # 1. Load existing data
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
        
    # 2. Append new draft
    new_draft = {
        "id": int(datetime.now().timestamp() * 1000),
        "title": title,
        "content": content,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    data.append(new_draft)
    
    # 3. Save back to disk
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)
    
    st.toast(f"Draft saved to Archives: {title}", icon="💾")
    return new_draft

def load_archives(username):
    """Loads all saved drafts for the user."""
    file_path = get_user_archive_path(username)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                # Load, then reverse order to show newest first
                return list(reversed(json.load(f)))
            except json.JSONDecodeError:
                return []
    return []

def delete_draft(username, draft_id):
    """Deletes a specific draft by ID."""
    file_path = get_user_archive_path(username)
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            data = json.load(f)
        
        # Filter out the deleted draft
        data = [d for d in data if d['id'] != draft_id]
        
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
        st.toast("Draft deleted.", icon="🗑️")
        st.rerun()