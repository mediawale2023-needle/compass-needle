#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

# THIS SECTION CONTAINS CRITICAL TESTING INSTRUCTIONS FOR BOTH AGENTS
# BOTH MAIN_AGENT AND TESTING_AGENT MUST PRESERVE THIS ENTIRE BLOCK

# Communication Protocol:
# If the `testing_agent` is available, main agent should delegate all testing tasks to it.
#
# You have access to a file called `test_result.md`. This file contains the complete testing state
# and history, and is the primary means of communication between main and the testing agent.
#
# Main and testing agents must follow this exact format to maintain testing data. 
# The testing data must be entered in yaml format Below is the data structure:
# 
## user_problem_statement: {problem_statement}
## backend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.py"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## frontend:
##   - task: "Task name"
##     implemented: true
##     working: true  # or false or "NA"
##     file: "file_path.js"
##     stuck_count: 0
##     priority: "high"  # or "medium" or "low"
##     needs_retesting: false
##     status_history:
##         -working: true  # or false or "NA"
##         -agent: "main"  # or "testing" or "user"
##         -comment: "Detailed comment about status"
##
## metadata:
##   created_by: "main_agent"
##   version: "1.0"
##   test_sequence: 0
##   run_ui: false
##
## test_plan:
##   current_focus:
##     - "Task name 1"
##     - "Task name 2"
##   stuck_tasks:
##     - "Task name with persistent issues"
##   test_all: false
##   test_priority: "high_first"  # or "sequential" or "stuck_first"
##
## agent_communication:
##     -agent: "main"  # or "testing" or "user"
##     -message: "Communication message between agents"

# Protocol Guidelines for Main agent
#
# 1. Update Test Result File Before Testing:
#    - Main agent must always update the `test_result.md` file before calling the testing agent
#    - Add implementation details to the status_history
#    - Set `needs_retesting` to true for tasks that need testing
#    - Update the `test_plan` section to guide testing priorities
#    - Add a message to `agent_communication` explaining what you've done
#
# 2. Incorporate User Feedback:
#    - When a user provides feedback that something is or isn't working, add this information to the relevant task's status_history
#    - Update the working status based on user feedback
#    - If a user reports an issue with a task that was marked as working, increment the stuck_count
#    - Whenever user reports issue in the app, if we have testing agent and task_result.md file so find the appropriate task for that and append in status_history of that task to contain the user concern and problem as well 
#
# 3. Track Stuck Tasks:
#    - Monitor which tasks have high stuck_count values or where you are fixing same issue again and again, analyze that when you read task_result.md
#    - For persistent issues, use websearch tool to find solutions
#    - Pay special attention to tasks in the stuck_tasks list
#    - When you fix an issue with a stuck task, don't reset the stuck_count until the testing agent confirms it's working
#
# 4. Provide Context to Testing Agent:
#    - When calling the testing agent, provide clear instructions about:
#      - Which tasks need testing (reference the test_plan)
#      - Any authentication details or configuration needed
#      - Specific test scenarios to focus on
#      - Any known issues or edge cases to verify
#
# 5. Call the testing agent with specific instructions referring to test_result.md
#
# IMPORTANT: Main agent must ALWAYS update test_result.md BEFORE calling the testing agent, as it relies on this file to understand what to test next.

#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================



#====================================================================================================
# Testing Data - Main Agent and testing sub agent both should log testing data below this section
#====================================================================================================

user_problem_statement: |
  Build an Admin Dashboard that allows admin to:
  1) Onboard new MPs
  2) Reset MP passwords
  3) Upload Election Commission polling-station PDFs
  4) Convert PDFs into JSON using pdfplumber (NO AI)
  5) Allow admin to manually edit JSON before saving
  6) Store constituency metadata as free-text JSON
  Also build a backend-only geography resolver that maps grievance text to Assembly/Parliamentary Constituency.

backend:
  - task: "Admin Dashboard - Streamlit App"
    implemented: true
    working: true
    file: "/app/admin_dashboard.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Created admin_dashboard.py with 3 tabs: MP Management, Geography Upload, Constituency Metadata"
      - working: true
        agent: "testing"
        comment: "Admin dashboard imports successfully. Streamlit dependencies installed and working. Ready for use with 'streamlit run admin_dashboard.py'."

  - task: "Geography Resolver - Backend Module"
    implemented: true
    working: true
    file: "/app/sansadx-backend/geography_resolver.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Created geography_resolver.py with deterministic location matching. Tested successfully with sample data."

  - task: "Geography Integration in Grievance Processing"
    implemented: true
    working: true
    file: "/app/sansadx-backend/main.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Integrated geography resolver into process_and_reply function. Added geography endpoints."
      - working: true
        agent: "testing"
        comment: "All geography API endpoints tested successfully. Server running on port 8000. All 6 test cases passed: /geography/stats, /geography/reload, /geography/resolve with various inputs including Muglihal location resolution, booth number resolution, and unknown location handling."

frontend:
  - task: "No frontend changes required"
    implemented: true
    working: "NA"
    file: "N/A"
    stuck_count: 0
    priority: "low"
    needs_retesting: false
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Admin Dashboard is a separate Streamlit app, not part of React frontend"

metadata:
  created_by: "main_agent"
  version: "1.0"
  test_sequence: 2
  run_ui: false

test_plan:
  current_focus: []
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: "Implemented Admin Dashboard (Streamlit) with 3 tabs and Geography Resolver backend. Ready for testing."
  - agent: "testing"
    message: "✅ TESTING COMPLETE: All backend components tested successfully. Geography Resolver API (sansadx-backend) running on port 8000 with all endpoints working correctly. Admin Dashboard imports successfully and ready for use. All high-priority tasks are now working."
  - agent: "main"
    message: |
      🧠 PHASE 1 OF NEEDLE BRAIN SHIPPED — PRS ANSWER INGESTION

      Problem: Parliamentary Sync was only scraping question metadata from PRS.
      `question_text` stored the PDF URL (not text) and `answer_text` was always
      empty. No Ministry replies were ever ingested.

      Solution (this commit):
        • modules/prs_answer_extractor.py — downloads PRS-linked Q&A PDFs,
          pdfplumber extraction + Gemini 2.5 Flash Vision OCR fallback,
          splits into individual Q&A blocks (supports STARRED / UNSTARRED /
          SHORT NOTICE headers, ministry detection, asker extraction).
        • jobs/parliament_answer_fetcher.py — DB-aware orchestrator with
          prs_pdf_cache table (download once, reuse), subject-similarity
          matcher (fuzzy ≥ 0.55, ministry boost), per-tenant + all-tenants
          entry points, coverage stats, CLI runner.
        • Schema: new columns question_pdf_url, real_question_number,
          answer_fetched_at, answer_fetch_status on parliamentary_questions;
          new table prs_pdf_cache. Idempotent migration runs on app startup
          (registered in main.py). One-off data move from question_text→
          question_pdf_url for rows holding a URL.
        • jobs/parliament_scraper.py — now writes PDF URL into the proper
          column, not into question_text.
        • admin_api.py — 5 new endpoints:
            GET  /api/admin/parliament/answer-coverage
            GET  /api/admin/parliament/answer-coverage/{tenant_id}
            POST /api/admin/parliament/fetch-answers/{tenant_id}
            POST /api/admin/parliament/fetch-answers-all
            GET  /api/admin/parliament/fetch-answers/status/{job_id}
            GET  /api/admin/parliament/question/{row_id}   (full Q+A detail)
        • admin/app/dashboard/parliament-sync/page.js — Answer Coverage
          strip (progress bar + stats), "🧠 Fetch Answers" button,
          expandable rows showing full Question + Ministry Answer + PDF
          source link + extractor method, AnswerStatusChip per row,
          background job polling.

      Smoke test (live PRS PDF, AU6230):
        ✓ 8-page PDF, 376 KB, extracted via pdfplumber
        ✓ Real Q No. 6230, type=unstarred, Ministry of Food Processing
        ✓ Parsed 8 joint-signatory MP names
        ✓ Full question text and full ministry reply by Shri Ravneet Singh

      Deployment note: this repo runs on Railway (Postgres + FastAPI).
      On next deploy main.py auto-runs ensure_schema() + migrate_question_text_urls().
      After deploy, admins click "🧠 Fetch Answers" per tenant OR run
      `python -m jobs.parliament_answer_fetcher --all` on the host.

      Next (Phase 2): pgvector + memory_chunks + OpenAI embeddings.