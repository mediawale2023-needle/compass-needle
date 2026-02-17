"import streamlit as st
from datetime import datetime
from contextlib import contextmanager

# Import database components from db.py
import sys
sys.path.insert(0, '/app')
from db import SessionLocal, Archive, DNASample, init_db

# --- DATABASE SESSION CONTEXT MANAGER ---
@contextmanager
def get_db_session():
    \"\"\"Context manager for database sessions to prevent connection leaks.\"\"\"
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

# --- ARCHIVE FUNCTIONS (Drafts) ---
def load_archives(username):
    \"\"\"Loads saved drafts for a specific user from PostgreSQL.\"\"\"
    with get_db_session() as db:
        archives = db.query(Archive).filter(Archive.user == username).all()
        # Return as list of dicts to maintain compatibility
        return [
            {
                \"id\": a.id,
                \"user\": a.user,
                \"date\": a.date,
                \"category\": a.category,
                \"title\": a.title,
                \"content\": a.content
            }
            for a in archives
        ]

def save_draft(username, title, content, category=\"General\"):
    \"\"\"Saves a draft to PostgreSQL.\"\"\"
    with get_db_session() as db:
        new_entry = Archive(
            user=username,
            date=datetime.now().strftime(\"%Y-%m-%d %H:%M\"),
            category=category,
            title=title,
            content=content
        )
        db.add(new_entry)
    
    st.toast(f\"Saved to Archives: {title}\", icon=\"💾\")

def delete_draft(username, draft_id):
    \"\"\"Deletes a draft by ID from PostgreSQL.\"\"\"
    with get_db_session() as db:
        db.query(Archive).filter(
            Archive.user == username,
            Archive.id == draft_id
        ).delete()

# --- DNA BANK FUNCTIONS (Style Templates) ---
def save_dna_sample(username, title, content):
    \"\"\"Saves a past letter as a style template to PostgreSQL.\"\"\"
    with get_db_session() as db:
        new_sample = DNASample(
            username=username,
            title=title,
            content=content
        )
        db.add(new_sample)

def load_dna_samples(username):
    \"\"\"Loads all style templates for the user from PostgreSQL.\"\"\"
    with get_db_session() as db:
        samples = db.query(DNASample).filter(DNASample.username == username).all()
        # Return as list of dicts to maintain compatibility
        return [
            {
                \"id\": s.id,
                \"username\": s.username,
                \"title\": s.title,
                \"content\": s.content
            }
            for s in samples
        ]

def delete_dna_sample(username, sample_id):
    \"\"\"Deletes a style template from PostgreSQL.\"\"\"
    with get_db_session() as db:
        db.query(DNASample).filter(
            DNASample.username == username,
            DNASample.id == sample_id
        ).delete()

# Initialize database tables on module import
init_db()
"