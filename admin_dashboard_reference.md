# Technical Reference: Needle Admin Dashboard

## 1. Overview
* **Purpose:** SaaS-style Admin Panel for onboarding MPs (Tenants) and digitizing Election Commission geography data.
* **File:** `admin_dashboard.py`
* **Tech Stack:** Streamlit, PDFPlumber, SQLAlchemy (Backend DB), Pandas.

## 2. Authentication Module
* **Login System:** Verifies credentials against the `User` table.
* **Roles:** strictly allows `['admin', 'super_admin', 'sysadmin']`.
* **Fail-safe:** If no admin exists in the DB, the system auto-creates a default user:
    * **Username:** `sysadmin`
    * **Password:** `admin123`
* **State:** Uses `st.session_state` to persist login across reloads.

## 3. Tab 1: MP Management (Multi-Tenancy)
* **Create Tenant:**
    * Creates a record in the `Tenant` table (Name, Constituency, Subscription).
    * Creates a record in the `User` table (Username, Password, Role='mp').
    * *Validation:* Checks for duplicate usernames before creation.
* **Password Reset:** Allows Admins to overwrite MP passwords securely.
* **Listing:** Displays all MPs (excluding admins) in a real-time Pandas DataFrame.

## 4. Tab 2: Geography Engine (Core Feature)
* **PDF Parsing:**
    * **Input:** Election Commission Polling Station PDFs.
    * **Extraction:** Uses `pdfplumber` to extract tables and text.
    * **Logic:** Identifies `Station Number`, `Locality`, and `Building Name` via regex.
    * **Cleaning:** automatically removes duplicates based on the station number.
* **JSON Editor:**
    * Provides a raw JSON editor in the browser to fix typos/errors before saving.
    * Includes automatic JSON Syntax Validation.
* **Storage & Sync:**
    * **Path:** Saves files to `data/geography/{Parliamentary_Name}/{Assembly_Name}.json`.
    * **Hot Reload:** Sends a `POST` request to `http://127.0.0.1:8000/geography/reload` immediately after saving. This updates the backend search index without a server restart.
* **File Management:**
    * View existing files grouped by Parliamentary constituency.
    * **Delete:** Admin can delete specific Assembly JSON files from the disk.

## 5. Tab 3: Metadata Manager
* **Purpose:** Manages static, non-geographic data (e.g., MP Party, Population, Key Issues).
* **Storage:** Single JSON file located at `data/constituency_metadata.json`.
* **Structure:** Key-Value pair where Key = Parliamentary Constituency Name.

## 6. Dependencies & Connections
* **Backend DB:** Imports `SessionLocal`, `Tenant`, `User` from `sansadx-backend.db`.
* **API:** Relies on the local API running at `http://127.0.0.1:8000` for hot-reloading.