"""
scripts/diagnose_prs_listing.py
Run this locally to inspect what HTML PRS India actually returns for the
MP listing page — so we can fix the global_parliament_crawler selectors.

Usage:
    python scripts/diagnose_prs_listing.py
"""

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://prsindia.org/",
}

URL = "https://prsindia.org/mptrack/18loksabha"

print(f"\nFetching: {URL}\n{'='*60}")
resp = requests.get(URL, headers=HEADERS, timeout=20)
print(f"Status: {resp.status_code}")
print(f"Content-Length: {len(resp.text)} chars")
print(f"Content-Type: {resp.headers.get('Content-Type', 'unknown')}\n")

soup = BeautifulSoup(resp.text, "html.parser")

# ── 1. Page title ──────────────────────────────────────────────────────────────
print(f"Title: {soup.title.string if soup.title else 'None'}\n")

# ── 2. All hrefs containing 'mptrack' or 'lok-sabha' ──────────────────────────
print("── Links containing 'mptrack' or 'lok-sabha' (first 30) ──")
found_links = 0
for a in soup.find_all("a", href=True):
    href = a["href"]
    if "mptrack" in href or "lok-sabha" in href.lower():
        print(f"  {href[:100]}  →  {a.get_text(strip=True)[:60]}")
        found_links += 1
        if found_links >= 30:
            print("  ... (truncated)")
            break
if found_links == 0:
    print("  (none found — page may require JavaScript rendering)")

# ── 3. All unique div/section/article class names ─────────────────────────────
print("\n── Unique class names on block-level tags ──")
class_counts: dict[str, int] = {}
for tag in soup.find_all(["div", "section", "article", "li", "tr", "td"]):
    for cls in tag.get("class", []):
        class_counts[cls] = class_counts.get(cls, 0) + 1

# Sort by frequency descending
for cls, count in sorted(class_counts.items(), key=lambda x: -x[1])[:50]:
    print(f"  .{cls:<40} ({count:3d} occurrences)")

# ── 4. Look for any table with MP-like data ────────────────────────────────────
print("\n── Tables on page ──")
tables = soup.find_all("table")
print(f"  Found {len(tables)} table(s)")
for i, tbl in enumerate(tables[:3]):
    headers = [th.get_text(strip=True) for th in tbl.find_all("th")]
    rows = tbl.find_all("tr")
    print(f"  Table {i+1}: {len(rows)} rows, headers: {headers}")
    # Print first data row
    if rows:
        first_row = rows[1] if len(rows) > 1 else rows[0]
        cells = [td.get_text(strip=True)[:40] for td in first_row.find_all(["td","th"])]
        print(f"    First row: {cells}")

# ── 5. Raw HTML snippet of first 3000 chars (body) ────────────────────────────
print("\n── First 3000 chars of <body> ──")
body = soup.find("body")
body_html = str(body)[:3000] if body else resp.text[:3000]
print(body_html)

# ── 6. Check if page looks like a JS SPA ─────────────────────────────────────
script_tags = soup.find_all("script")
print(f"\n── Script tags: {len(script_tags)} found ──")
for s in script_tags[:5]:
    src = s.get("src", "")
    if src:
        print(f"  {src[:100]}")
    else:
        txt = s.get_text()[:200].strip()
        if txt:
            print(f"  Inline: {txt[:120]}")

# ── 7. Try page=1 with different pagination param ────────────────────────────
print(f"\n── Trying alternate URL: {URL}?page=0 ──")
resp2 = requests.get(URL + "?page=0", headers=HEADERS, timeout=20)
print(f"  Status: {resp2.status_code}, Length: {len(resp2.text)}")
same = resp2.text[:500] == resp.text[:500]
print(f"  Same as page=1? {same}")

print("\n── Done. Paste output back to Claude. ──\n")
