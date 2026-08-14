"""
modules/govt_sync — Government Department Sync.

Staff-assisted pipeline for forwarding constituent grievances to state
grievance portals (Sampark, Jansunwai/IGRS, CPGRAMS, etc.) and syncing
status back to the Needle dashboard and constituent WhatsApp thread.

Design principle: AI does everything that's translation/classification.
A human does the two things a portal built specifically to require a
human for — solving the CAPTCHA, entering the OTP.

Architecture: Needle's backend runs on a real, persistent EC2 host (not an
ephemeral Railway container), so `browser_session.py` runs an actual
headless Chromium session per case there, auto-fills every field it has a
calibrated selector for (see modules/data/govt_portals.json
`field_schema.selectors` — hand-verified per portal, same rule as
`department_taxonomy`: never inferred, a wrong one fails closed with a
warning rather than silently misfiling), and streams the live page to the
staff dashboard over a WebSocket (CDP screencast) with mouse/keyboard
relayed back into the real page. Staff watch the real portal, solve the
CAPTCHA/OTP, and click Submit themselves — everything up to that point was
already filled in.

Because live sessions live in one process's memory, they only run on the
single-worker `backend_govt_live` service (see deploy/ec2/docker-compose.yml
and Caddyfile) — the normal multi-worker `backend` would randomly 404 a
session's WebSocket if it landed on a different worker than the one that
opened it.

A portal with no selectors calibrated yet still works — autofill just
no-ops per field and reports it, so staff type that field by hand in the
same live view rather than the feature being blocked until someone finishes
the "30-minute DOM inspection" the field_schema comments call for.

Submodules:
  translator.py     — AI translation layer (grievance -> PortalSubmission)
  adapters/          — status-check adapter per portal type (common interface)
  browser_session.py — live Playwright sessions: autofill, CDP screencast, input relay
  poller.py          — scheduled status polling for submitted grievances
  forward.py         — one-click "forward status update to citizen" via WhatsApp
  seed.py            — seeds/upserts govt_portals rows from modules/data/govt_portals.json
"""
