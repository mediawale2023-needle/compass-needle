import streamlit as st
import json
import os
from datetime import datetime

ARCHIVE_FILE = "user_archives.json"
DNA_FILE = "dna_bank.json"

# --- ARCHIVE FUNCTIONS (Drafts) ---
def load_archives(username):
    """Loads saved drafts for a specific user."""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r') as f:
            try:
                all_data = json.load(f)
                return [d for d in all_data if d.get('user') == username]
            except:
                return []
    return []

def save_draft(username, title, content, category="General"):
    """Saves a draft to the JSON file."""
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

def delete_draft(username, draft_id):
    """Deletes a draft by ID."""
    if os.path.exists(ARCHIVE_FILE):
        with open(ARCHIVE_FILE, 'r') as f:
            data = json.load(f)
        
        # Filter out the deleted one
        data = [d for d in data if not (d.get('user') == username and d['id'] == draft_id)]
        
        with open(ARCHIVE_FILE, 'w') as f:
            json.dump(data, f, indent=4)

# --- DNA BANK FUNCTIONS (Style Templates) ---
def init_dna_bank():
    if not os.path.exists(DNA_FILE):
        with open(DNA_FILE, "w") as f:
            json.dump([], f)

def save_dna_sample(username, title, content):
    """Saves a past letter as a style template."""
    init_dna_bank()
    with open(DNA_FILE, "r") as f:
        bank = json.load(f)
    
    new_sample = {
        "id": int(datetime.now().timestamp()),
        "username": username,
        "title": title,
        "content": content
    }
    bank.append(new_sample)
    
    with open(DNA_FILE, "w") as f:
        json.dump(bank, f)

def load_dna_samples(username):
    """Loads all style templates for the user."""
    init_dna_bank()
    with open(DNA_FILE, "r") as f:
        try:
            bank = json.load(f)
            return [doc for doc in bank if doc["username"] == username]
        except:
            return []

def delete_dna_sample(username, sample_id):
    """Deletes a style template."""
    init_dna_bank()
    with open(DNA_FILE, "r") as f:
        bank = json.load(f)
    
    bank = [doc for doc in bank if not (doc["username"] == username and doc["id"] == sample_id)]
    
    with open(DNA_FILE, "w") as f:
        json.dump(bank, f)