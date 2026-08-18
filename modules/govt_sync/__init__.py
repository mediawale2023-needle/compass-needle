"""
modules/govt_sync — Government Department Sync.

Staff-assisted pipeline for forwarding constituent grievances to state
grievance portals (Sampark, Jansunwai/IGRS, CPGRAMS, etc.) and syncing
status back to the Needle dashboard and constituent WhatsApp thread.

Design principle: AI translates/classifies the grievance into a worksheet
(department, subject, description). A human does everything on the actual
government form — logging in, typing every field, solving the CAPTCHA,
entering the OTP, clicking Submit. No field is ever auto-filled; that was
tried and deliberately removed (see modules/govt_sync/browser_session.py's
module docstring and PROJECT_MEMORY.md for why).

Architecture: Needle's backend runs on a real, persistent EC2 host (not an
ephemeral Railway container), so `browser_session.py` runs an actual
headless Chromium session per case there, opens the real portal, and streams
the live page to the staff dashboard over a WebSocket (CDP screencast) with
mouse/keyboard relayed back into the real page. If a portal's post-login
grievance-form URL is configured (`field_schema.post_login_entry_path`), the
session auto-navigates there once staff finish logging in — that is the
extent of the automation. Staff read the AI worksheet (shown as copy-paste
text in Briefcase) and type it into the real form themselves.

Because live sessions live in one process's memory, they only run on the
single-worker `backend_govt_live` service (see deploy/ec2/docker-compose.yml
and Caddyfile) — the normal multi-worker `backend` would randomly 404 a
session's WebSocket if it landed on a different worker than the one that
opened it.

`GOVT_LIVE_AUTOMATION_ENABLED` (default on) is an emergency off switch for
opening live sessions at all — every session runs from the one shared EC2
IP across every tenant/state, so it's kept as a lever in case a specific
portal ever blocks or rate-limits that IP. It does not gate autofill; there
is nothing left to gate there.

Submodules:
  translator.py     — AI translation layer (grievance -> PortalSubmission)
  adapters/          — status-check adapter per portal type (common interface)
  browser_session.py — live Playwright sessions: open, auto-navigate post-login, CDP screencast, input relay
  poller.py          — scheduled status polling for submitted grievances
  forward.py         — one-click "forward status update to citizen" via WhatsApp
  seed.py            — seeds/upserts govt_portals rows from modules/data/govt_portals.json
"""
