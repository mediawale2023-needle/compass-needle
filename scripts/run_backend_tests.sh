#!/usr/bin/env bash
# Run the backend suite one test FILE per pytest process.
#
# The test files are architected for per-file isolation: each owns a private
# SQLite database and patches module-level engine/SessionLocal bindings at
# import time. Running them all in one process makes those patches collide
# (whichever file imported last wins), producing ~17 cross-file failures that
# do not exist in any file on its own. Until the harnesses share one fixture,
# per-file processes are the honest way to run what the tests actually assert.
set -u
PY="${PYTHON_BIN:-venv/bin/python}"
failed=()
for f in tests/test_*.py; do
  echo "── ${f}"
  out=$("$PY" -m pytest "$f" -q 2>&1)
  rc=$?
  echo "$out"
  # Exit 5 = "no tests collected". That is a failure, EXCEPT for an opt-in file that skipped itself at
  # module level (e.g. real-PostgreSQL files without their NEEDLE_*_PG_URL), which reports "skipped".
  if [ "$rc" -ne 0 ] && ! { [ "$rc" -eq 5 ] && grep -qE '[0-9]+ skipped' <<<"$out"; }; then
    failed+=("$f")
  fi
  # Per-file sqlite artifacts (test files create them in the repo root)
  rm -f ./*.db 2>/dev/null || true
done
# Repo data files some tests dirty through the dev JSON fallback save path.
git checkout -- data/geography 2>/dev/null || true

if [ "${#failed[@]}" -gt 0 ]; then
  echo ""
  echo "FAILED files:"
  printf ' - %s\n' "${failed[@]}"
  exit 1
fi
echo ""
echo "All backend test files passed."
