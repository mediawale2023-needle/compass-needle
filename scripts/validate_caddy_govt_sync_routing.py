#!/usr/bin/env python3
"""
scripts/validate_caddy_govt_sync_routing.py — real Caddy routing regression
test for the govt-sync fixation plan Step 4 correction, and (2026-08-26)
every govt/session live-session action from the production-readiness
review's K6 finding.

WHY THIS EXISTS: Caddy's `path` matcher wildcard (`*`) only spans one path
segment, never crosses a `/`. The first Step 4 attempt used one trailing-
wildcard pattern for both /status-check/start and
/status-check/{attempt_id}/advance, which silently only matched the first
one — caught by sending real request paths through a real Caddy instance,
not by syntax validation (`caddy validate` passed on the broken version) or
by grepping the compiled JSON for a substring (that also "passed" — the
pattern string genuinely was present, it just didn't match what it needed
to). This script is that same check, kept as a permanent, re-runnable
regression test.

K6 EXTENSION: a second, related but distinct Caddy behavior was found the
same way — a pattern with two or more wildcards forces EVERY wildcard in
it, including a trailing one, to match exactly one path segment (a LONE
trailing wildcard, by contrast, spans the rest of the path). The old
`/api/cases/*/govt/session/*` (two wildcards) covered `.../session/start`
but silently missed `.../session/{id}/close` and
`.../session/{id}/capture-reference`; `/api/govt/sessions` and
`/api/govt/sessions/close-all` never matched at all (the old pattern's
literal segment was singular "session", the real routes are plural
"sessions"). The CASES list below covers every one of those routes so this
class of gap can't silently reappear.

WHAT IT ACTUALLY TESTS: the exact `@govt_live path ...` matcher line is
extracted VERBATIM from deploy/ec2/Caddyfile at run time (never retyped by
hand, so it can't silently drift from the real file) and dropped into a
minimal, HTTP-only wrapper site — the real file's `api.theneedle.in` block
needs real TLS/DNS to run at all, which isn't testable locally, but the
routing logic under test lives entirely in that one matcher line plus the
two reverse_proxy directives, both copied verbatim too. Two dummy upstream
containers named exactly `backend` and `backend_govt_live` (the same
hostnames the real docker-compose.yml uses) sit on an isolated Docker
network, so Caddy's own DNS resolution sends traffic to whichever one
actually matches — no manual routing simulation, no assumptions.

REQUIRES: Docker. Not part of `pytest tests/` (this needs real containers,
not just Python) — run by hand before/after any change to
deploy/ec2/Caddyfile's routing:

    python3 scripts/validate_caddy_govt_sync_routing.py

Exits 0 and prints "ALL ROUTING CHECKS PASSED" on success; exits 1 and
prints exactly which path(s) reached the wrong upstream on failure. Always
tears down its own containers/network/temp files, even on failure.
"""
import os
import subprocess
import sys
import time
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CADDYFILE = os.path.join(REPO_ROOT, "deploy/ec2/Caddyfile")
NETWORK = "caddy-routing-validate-net"
CADDY_CONTAINER = "caddy-routing-validate"
CADDY_PORT = 18081  # host-side port for this run — arbitrary, just needs to be free

DUMMY_SERVER_SRC = '''
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

NAME = sys.argv[1]

class H(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("X-Served-By", NAME)
        self.end_headers()
        self.wfile.write(NAME.encode())
    def do_POST(self):
        self.do_GET()
    def log_message(self, *a):
        pass

HTTPServer(("0.0.0.0", 8000), H).serve_forever()
'''

# (method, request path, expected upstream container name)
CASES = [
    ("POST", "/api/cases/20/govt/status-check/start", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/status-check/4a5f3b99ce874e798024ed16f846784a/advance", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/session/start", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/poll", "backend"),
    ("POST", "/api/cases/20/govt/submit", "backend"),
    # K6 — every govt/session live-session action, real Caddy semantics only
    ("GET", "/api/govt/sessions", "backend_govt_live"),
    ("POST", "/api/govt/sessions/close-all", "backend_govt_live"),
    ("POST", "/api/govt/sessions/abc123/close", "backend_govt_live"),
    ("GET", "/api/govt/session/abc123/stream", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/session/abc123/capture-reference", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/session/abc123/close", "backend_govt_live"),
    # Tamil Nadu status-check live session (2026-09-02) — regression case for
    # the exact gap this script exists to catch: these two routes shipped
    # without being added to @govt_live, so start-status-check silently fell
    # through to the multi-worker `backend` below while its /stream WebSocket
    # correctly landed on backend_govt_live — two different processes, so the
    # live browser view never found its own session and hung on "Connecting…".
    ("POST", "/api/cases/20/govt/session/start-status-check", "backend_govt_live"),
    ("POST", "/api/cases/20/govt/session/abc123/tamil-nadu/check-status", "backend_govt_live"),
]


def run(cmd):
    return subprocess.run(cmd, check=True, capture_output=True, text=True)


def cleanup():
    subprocess.run(["docker", "rm", "-f", "backend", "backend_govt_live", CADDY_CONTAINER],
                    capture_output=True)
    subprocess.run(["docker", "network", "rm", NETWORK], capture_output=True)


def extract_govt_live_block(caddyfile_path: str) -> tuple[str, str, str]:
    """Pulls the @govt_live matcher line and both reverse_proxy lines
    verbatim out of the real Caddyfile — never retyped, so this test can
    never silently test something other than what's actually committed."""
    with open(caddyfile_path) as f:
        lines = [l.strip() for l in f.readlines()]
    matcher_line = next(l for l in lines if l.startswith("@govt_live path"))
    govt_live_proxy = next(l for l in lines if l.startswith("reverse_proxy @govt_live"))
    default_proxy = next(l for l in lines if l.startswith("reverse_proxy ") and "@govt_live" not in l)
    return matcher_line, govt_live_proxy, default_proxy


def main():
    cleanup()  # in case a previous run didn't clean up
    tmp_dir = "/tmp/caddy_routing_validate"
    os.makedirs(tmp_dir, exist_ok=True)
    dummy_path = os.path.join(tmp_dir, "dummy_upstream.py")
    wrapper_path = os.path.join(tmp_dir, "Caddyfile")

    with open(dummy_path, "w") as f:
        f.write(DUMMY_SERVER_SRC)

    matcher_line, govt_live_proxy, default_proxy = extract_govt_live_block(CADDYFILE)
    print("Extracted verbatim from deploy/ec2/Caddyfile:")
    print(f"  {matcher_line}")
    print(f"  {govt_live_proxy}")
    print(f"  {default_proxy}")
    print()

    with open(wrapper_path, "w") as f:
        f.write(f":8080 {{\n\t{matcher_line}\n\t{govt_live_proxy}\n\n\t{default_proxy}\n}}\n")

    try:
        run(["docker", "network", "create", NETWORK])

        for name in ("backend", "backend_govt_live"):
            run([
                "docker", "run", "-d", "--rm", "--name", name, "--network", NETWORK,
                "-v", f"{dummy_path}:/dummy.py:ro",
                "python:3.11-slim", "python", "/dummy.py", name,
            ])

        run([
            "docker", "run", "-d", "--rm", "--name", CADDY_CONTAINER,
            "--network", NETWORK, "-p", f"{CADDY_PORT}:8080",
            "-v", f"{wrapper_path}:/etc/caddy/Caddyfile:ro",
            "caddy:2",
        ])

        time.sleep(2.5)

        failures = []
        for method, path, expected in CASES:
            url = f"http://localhost:{CADDY_PORT}{path}"
            req = urllib.request.Request(url, method=method, data=b"" if method == "POST" else None)
            try:
                with urllib.request.urlopen(req, timeout=5) as resp:
                    served_by = resp.headers.get("X-Served-By")
            except Exception as e:
                served_by = f"<request failed: {e}>"

            status = "OK" if served_by == expected else "FAIL"
            print(f"[{status}] {method:5s} {path}")
            print(f"         expected={expected!r} actual={served_by!r}")
            if served_by != expected:
                failures.append((f"{method} {path}", expected, served_by))

        print()
        if failures:
            print(f"{len(failures)} of {len(CASES)} routing checks FAILED:")
            for path, expected, actual in failures:
                print(f"  - {path}: expected {expected!r}, got {actual!r}")
            sys.exit(1)
        else:
            print(f"ALL {len(CASES)} ROUTING CHECKS PASSED")
    finally:
        for p in (dummy_path, wrapper_path):
            if os.path.exists(p):
                os.remove(p)
        cleanup()


if __name__ == "__main__":
    main()
