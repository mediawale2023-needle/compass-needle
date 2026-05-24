"""
Geography Resolver (MULTI-TENANT)
1. Checks tenant-specific DB overrides (per tenant_id).
2. Filters junk polling-sheet/meta rows before indexing.
3. Exact/alias substring match against geography index.
4. Spaceless Match (Fixes "Shahunagar" vs "Shahu Nagar").
5. Fuzzy Typos Match (Fixes "Tilkwadi" vs "Tilakwadi").
"""

import json
import logging
import unicodedata
from pathlib import Path
from typing import Dict, Any, Optional, Iterable, Set
import re
import string
from difflib import SequenceMatcher

# ==========================================
# INDIC TRANSLITERATION
# ==========================================

# Simplified Devanagari → Roman map sufficient for Indian location names.
# Covers consonants, vowels, matras, and common nukta variants.
_DEVA_MAP = {
    # Vowels (independent)
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'ऋ': 'ri', 'अं': 'an',
    # Consonants
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'n',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh',
    'ष': 'sh', 'स': 's', 'ह': 'h', 'ळ': 'l', 'क्ष': 'ksh', 'ज्ञ': 'gya',
    # Nukta variants (ड़, ढ़, etc.)
    'ड़': 'r', 'ढ़': 'rh', 'ज़': 'z', 'फ़': 'f', 'ग़': 'g', 'ख़': 'kh',
    # Matras (vowel signs attached to consonants)
    'ा': 'a', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ृ': 'ri',
    # Anusvara / visarga / halant
    'ं': 'n', 'ँ': 'n', 'ः': 'h', '्': '',
    # Digits
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
}

# Devanagari Unicode range: U+0900–U+097F
_DEVA_RE = re.compile(r'[\u0900-\u097F]')

# Simplified Kannada → Roman map for locality names. This is intentionally
# conservative: it exists to ground geography, not to produce pretty language.
_KANNADA_MAP = {
    # Independent vowels
    'ಅ': 'a', 'ಆ': 'aa', 'ಇ': 'i', 'ಈ': 'ee', 'ಉ': 'u', 'ಊ': 'oo',
    'ಋ': 'ri', 'ಎ': 'e', 'ಏ': 'e', 'ಐ': 'ai', 'ಒ': 'o', 'ಓ': 'o', 'ಔ': 'au',
    # Consonants
    'ಕ': 'k', 'ಖ': 'kh', 'ಗ': 'g', 'ಘ': 'gh', 'ಙ': 'ng',
    'ಚ': 'ch', 'ಛ': 'chh', 'ಜ': 'j', 'ಝ': 'jh', 'ಞ': 'ny',
    'ಟ': 't', 'ಠ': 'th', 'ಡ': 'd', 'ಢ': 'dh', 'ಣ': 'n',
    'ತ': 't', 'ಥ': 'th', 'ದ': 'd', 'ಧ': 'dh', 'ನ': 'n',
    'ಪ': 'p', 'ಫ': 'ph', 'ಬ': 'b', 'ಭ': 'bh', 'ಮ': 'm',
    'ಯ': 'y', 'ರ': 'r', 'ಱ': 'r', 'ಲ': 'l', 'ಳ': 'l', 'ವ': 'v',
    'ಶ': 'sh', 'ಷ': 'sh', 'ಸ': 's', 'ಹ': 'h',
    # Vowel signs
    'ಾ': 'a', 'ಿ': 'i', 'ೀ': 'ee', 'ು': 'u', 'ೂ': 'oo', 'ೃ': 'ri',
    'ೆ': 'e', 'ೇ': 'e', 'ೈ': 'ai', 'ೊ': 'o', 'ೋ': 'o', 'ೌ': 'au',
    # Marks / virama
    'ಂ': 'n', 'ಃ': 'h', '್': '',
    # Digits
    '೦': '0', '೧': '1', '೨': '2', '೩': '3', '೪': '4',
    '೫': '5', '೬': '6', '೭': '7', '೮': '8', '೯': '9',
}

_KANNADA_RE = re.compile(r'[\u0C80-\u0CFF]')


def _is_devanagari(text: str) -> bool:
    return bool(_DEVA_RE.search(text))


def _has_indic_script(text: str) -> bool:
    return bool(_DEVA_RE.search(text) or _KANNADA_RE.search(text))


def _transliterate(text: str) -> str:
    """
    Convert supported Indic scripts to a simplified Roman form suitable for
    fuzzy matching against casual English spellings of Indian place names.
    Unsupported Indic characters pass through unchanged.
    """
    # Multi-char sequences first (nukta composites, conjuncts)
    for deva, roman in sorted(_DEVA_MAP.items(), key=lambda x: -len(x[0])):
        text = text.replace(deva, roman)
    for kannada, roman in sorted(_KANNADA_MAP.items(), key=lambda x: -len(x[0])):
        text = text.replace(kannada, roman)
    # Remove any remaining supported-script characters not in the map
    text = _DEVA_RE.sub('', text)
    text = _KANNADA_RE.sub('', text)
    return text.strip()

# --- CONFIG & PATHS ---
CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent

POSSIBLE_PATHS = [
    CURRENT_DIR / "data" / "geography",
    PROJECT_ROOT / "data" / "geography",
    Path("data/geography").resolve()
]

GEOGRAPHY_BASE_PATH = None
for p in POSSIBLE_PATHS:
    if p.exists():
        GEOGRAPHY_BASE_PATH = p
        break

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_META_LOCALITY_VALUES = {
    "district",
    "total",
    "page",
    "part",
    "list",
}

_META_LOCALITY_PATTERNS = [
    re.compile(r"^\d+\s*\.\s*average number of voters per polling station$", re.IGNORECASE),
    re.compile(r"^\d+\s*average number of voters per polling station$", re.IGNORECASE),
    re.compile(r"^average number of voters per polling station$", re.IGNORECASE),
    re.compile(r"^(sl|serial)\.?\s*(no|number)\.?\s*$", re.IGNORECASE),
    re.compile(r"^polling station$", re.IGNORECASE),
    re.compile(r"^name of polling station$", re.IGNORECASE),
    re.compile(r"^total number of voters$", re.IGNORECASE),
]

_WORD_ALIAS_REPLACEMENTS = {
    "rd": "road",
    "rod": "road",
}

_ROMAN_LOCATION_SUFFIXES = (
    "inlli", "nlli",
    "nalli", "inalli", "dalli", "alli", "yalli",
    "madhe", "madhye",
)

# ==========================================
# TENANT-AWARE OVERRIDES (loaded from tenant_overrides.json)
# ==========================================

def _load_tenant_overrides(tenant_id):
    """Load geo_overrides for a tenant.

    Reads from the DB (primary — survives Railway redeploys) and falls back
    to tenant_overrides.json if the DB query fails.
    """
    # Primary: read geo_override rows from DB
    try:
        from sansadx_backend.db import SessionLocal, TenantOverride
        _db = SessionLocal()
        try:
            rows = _db.query(TenantOverride).filter(
                TenantOverride.override_type == "geo_override",
                TenantOverride.tenant_id == tenant_id,
            ).all()
            if rows:
                return {r.key: r.value for r in rows}
        finally:
            _db.close()
    except Exception:
        pass

    # Fallback: tenant_overrides.json (for local dev without DB)
    for op in [
        PROJECT_ROOT / "tenant_overrides.json",
        Path("tenant_overrides.json").resolve(),
        Path("/app/tenant_overrides.json"),
    ]:
        if op.exists():
            try:
                with open(op, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return data.get("geo_overrides", {}).get(str(tenant_id), {})
            except Exception:
                pass
    return {}


def _load_tenant_geo_aliases(tenant_id: int) -> dict[str, dict[str, str]]:
    """Load DB-backed generated geography aliases for a tenant."""
    try:
        from sansadx_backend.db import SessionLocal, TenantOverride
        _db = SessionLocal()
        try:
            rows = _db.query(TenantOverride).filter(
                TenantOverride.override_type == "geo_alias",
                TenantOverride.tenant_id == tenant_id,
            ).all()
            aliases: dict[str, dict[str, str]] = {}
            for row in rows:
                try:
                    payload = json.loads(row.value) if isinstance(row.value, str) else row.value
                except Exception:
                    payload = {}
                if isinstance(payload, dict):
                    assembly = str(payload.get("assembly") or "").strip()
                    display = str(payload.get("display") or row.key or "").strip()
                else:
                    assembly = str(row.value or "").strip()
                    display = str(row.key or "").strip()
                if assembly:
                    aliases[str(row.key or "").strip()] = {
                        "assembly": assembly,
                        "display": display or str(row.key or "").strip(),
                    }
            return aliases
        finally:
            _db.close()
    except Exception:
        return {}


_geography_index = {
    "assemblies": {},
    "ambiguities": {},
    "loaded": False
}

# --- HELPERS ---
def normalize(text: str) -> str:
    """Standardizes text: lower, no punctuation, single spaces."""
    if not text: return ""
    text = text.translate(str.maketrans('', '', string.punctuation))
    return re.sub(r"\s+", " ", text.lower().strip())


def _is_meta_locality(text: str) -> bool:
    value = normalize(text)
    if not value:
        return True
    if value in _META_LOCALITY_VALUES:
        return True
    return any(pattern.match(value) for pattern in _META_LOCALITY_PATTERNS)


def _canonicalize_alias(text: str) -> str:
    value = normalize(text)
    if not value:
        return ""

    words = [_WORD_ALIAS_REPLACEMENTS.get(word, word) for word in value.split()]
    value = " ".join(words)
    # Speech-to-text and transliteration often drift on Indian place names:
    # "Shanti" may become "Santi", and "Bastwad/Bastawad" may become "Baswad".
    # Keep these only as extra canonical forms; the original forms remain indexed.
    value = re.sub(r"\bsh", "s", value)
    value = value.replace("bastawad", "baswad")
    value = value.replace("bastwad", "baswad")
    value = value.replace("basawad", "baswad")
    value = value.replace("bsvad", "baswad")
    value = re.sub(r"(aa|ae)", "a", value)
    value = re.sub(r"(ee|ii)", "i", value)
    value = re.sub(r"(oo|uu)", "u", value)
    value = re.sub(r"(?<=[aeiou])y(?=[aeiou])", "", value)
    value = re.sub(r"iya\b", "ia", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _build_location_token_variants(value: str) -> Set[str]:
    variants: Set[str] = set()
    for token in normalize(value).split():
        if len(token) < 5:
            continue
        candidates = {token}
        for suffix in _ROMAN_LOCATION_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 5:
                candidates.add(token[: -len(suffix)])

        expanded = set(candidates)
        for candidate in candidates:
            expanded.add(candidate.replace("gundri", "kundri"))
            expanded.add(candidate.replace("kundri", "gundri"))
        variants.update(v for v in expanded if len(v) >= 5)
    return variants


def _build_match_forms(*texts: str) -> Set[str]:
    forms: Set[str] = set()
    for text in texts:
        if not text:
            continue
        normalized = normalize(text)
        if normalized:
            forms.add(normalized)
            canonical = _canonicalize_alias(text)
            if canonical:
                forms.add(canonical)
        if _has_indic_script(text):
            transliterated = normalize(_transliterate(text))
            if transliterated:
                forms.add(transliterated)
                canonical = _canonicalize_alias(transliterated)
                if canonical:
                    forms.add(canonical)
                forms.update(_build_location_token_variants(transliterated))
                forms.update(_build_location_token_variants(canonical))
    return {form for form in forms if form}


def _station_seed_aliases(station: Dict[str, Any], parliamentary_constituency: Optional[str] = None) -> Set[str]:
    seeds: Set[str] = set()
    for field in ("locality", "locality_en", "mentioned_location_roman", "mentioned_location_original"):
        value = str(station.get(field) or "").replace("\n", " ").strip()
        if value:
            seeds.add(value)

    raw_aliases = station.get("aliases") or station.get("alias") or []
    if isinstance(raw_aliases, str):
        raw_aliases = re.split(r"[,;|]", raw_aliases)
    if isinstance(raw_aliases, (list, tuple, set)):
        for alias in raw_aliases:
            value = str(alias or "").replace("\n", " ").strip()
            if value:
                seeds.add(value)

    for seed in list(seeds):
        seeds.update(_derive_locality_aliases(seed, parliamentary_constituency))
    return {seed for seed in seeds if seed and not _is_meta_locality(seed)}


def _generated_alias_forms(station: Dict[str, Any], parliamentary_constituency: Optional[str] = None) -> Set[str]:
    forms: Set[str] = set()
    for seed in _station_seed_aliases(station, parliamentary_constituency):
        forms.update(_build_match_forms(seed))
    return {form for form in forms if len(form) >= 4 and not _is_meta_locality(form)}


def _derive_locality_aliases(locality: str, parliamentary_constituency: Optional[str] = None) -> Set[str]:
    """Create safe short aliases from EC roll localities such as "Shahapur Belagavi"."""
    raw = (locality or "").replace("\n", " ").strip()
    if not raw:
        return set()

    parl = normalize(parliamentary_constituency or "")
    candidates = {raw}
    candidates.update(part.strip() for part in re.split(r"[,;/]", raw) if part.strip())

    aliases: Set[str] = set()
    for candidate in candidates:
        value = normalize(candidate)
        if not value or _is_meta_locality(value):
            continue

        if parl and value.endswith(f" {parl}"):
            stripped = value[: -len(parl)].strip()
            if stripped:
                value = stripped

        words = value.split()
        if parl:
            parl_words = parl.split()
            while words and words[-1] in parl_words:
                words = words[:-1]
            value = " ".join(words)

        if len(value) >= 5 and value not in {"east", "west", "north", "south", "ward", "room", "hall"}:
            aliases.add(value)
            words = value.split()
            if len(words) > 1 and words[-1] in {"kh", "bk", "k", "b"}:
                code_stripped = " ".join(words[:-1]).strip()
                if len(code_stripped) >= 5:
                    aliases.add(code_stripped)
            generic_prefixes = {
                "bazar", "bazaar", "peth", "pet", "galli", "gali", "wadi", "wada",
                "nagar", "road", "marg", "maharaj", "depot", "circle", "school",
                "college", "primary", "high", "govt", "government",
            }
            for index in range(1, len(words)):
                suffix_words = words[index:]
                suffix = " ".join(suffix_words)
                if len(suffix) < 5:
                    continue
                if suffix_words[0] in generic_prefixes:
                    continue
                aliases.add(suffix)

    return aliases


def _display_location_name(value: str) -> str:
    normalized = normalize(value)
    if not normalized:
        return value or ""
    return " ".join(word.capitalize() for word in normalized.split())


def _spaceless_forms(forms: Iterable[str]) -> Set[str]:
    return {form.replace(" ", "") for form in forms if form}


def _spaceless_phrase_forms(forms: Iterable[str], min_chars: int = 8) -> Set[str]:
    """Build adjacent 2-3 word location phrase forms for voice-note fuzzy matching."""
    phrases: Set[str] = set()
    for form in forms:
        words = [word for word in normalize(form).split() if len(word) >= 3]
        for size in (2, 3):
            if len(words) < size:
                continue
            for index in range(0, len(words) - size + 1):
                phrase = "".join(words[index:index + size])
                if len(phrase) >= min_chars:
                    phrases.add(phrase)
    return phrases


def _init_empty_index() -> None:
    _geography_index["assemblies"] = {}
    _geography_index["ambiguities"] = {}
    _geography_index["loaded"] = False


def _register_entry_ambiguities(parliamentary_constituency: str, assembly: str, forms: Set[str]) -> None:
    parl_key = normalize(parliamentary_constituency)
    parl_map = _geography_index["ambiguities"].setdefault(parl_key, {})
    for form in forms:
        if not form:
            continue
        parl_map.setdefault(form, set()).add(assembly)


def _collect_constituency_ambiguities(
    parliamentary_constituency: str,
    assembly: str,
    stations: Iterable[Dict[str, Any]],
    other_rows: Iterable[Dict[str, Any]],
) -> Dict[str, list]:
    current_forms = {}
    for station in stations:
        locality = (station.get("locality") or "").replace("\n", " ").strip()
        if not locality or _is_meta_locality(locality):
            continue
        forms = _build_match_forms(locality, station.get("locality_en", ""))
        for form in forms:
            current_forms.setdefault(form, locality)

    collisions: Dict[str, Set[str]] = {}
    for row in other_rows:
        if normalize(row.get("parliamentary_constituency", "")) != normalize(parliamentary_constituency):
            continue
        if row.get("assembly") == assembly:
            continue
        for station in row.get("stations") or []:
            locality = (station.get("locality") or "").replace("\n", " ").strip()
            if not locality or _is_meta_locality(locality):
                continue
            for form in _build_match_forms(locality, station.get("locality_en", "")):
                if form in current_forms:
                    collisions.setdefault(current_forms[form], set()).add(row.get("assembly", ""))

    return {
        locality: sorted(assemblies)
        for locality, assemblies in sorted(collisions.items())
        if assemblies
    }


def sanitize_and_validate_stations(
    stations: Iterable[Dict[str, Any]],
    *,
    parliamentary_constituency: Optional[str] = None,
    assembly: Optional[str] = None,
    other_rows: Optional[Iterable[Dict[str, Any]]] = None,
) -> tuple[list[Dict[str, Any]], Dict[str, Any]]:
    cleaned: list[Dict[str, Any]] = []
    removed_meta_rows: list[str] = []
    duplicate_localities_in_upload: Dict[str, int] = {}
    missing_locality_en_samples: list[str] = []
    locality_counts: Dict[str, int] = {}

    for index, raw_station in enumerate(stations or []):
        locality = (raw_station.get("locality") or "").replace("\n", " ").strip()
        if not locality:
            continue
        if _is_meta_locality(locality):
            removed_meta_rows.append(locality)
            continue

        normalized_locality = normalize(locality)
        locality_counts[normalized_locality] = locality_counts.get(normalized_locality, 0) + 1

        station_number = str(raw_station.get("station_number") or len(cleaned) + 1).strip() or str(len(cleaned) + 1)
        building_name = (raw_station.get("building_name") or locality).replace("\n", " ").strip()
        locality_en = (raw_station.get("locality_en") or "").replace("\n", " ").strip()

        if not locality_en and len(missing_locality_en_samples) < 20:
            missing_locality_en_samples.append(locality)

        cleaned_station = {
            "station_number": station_number,
            "locality": locality,
            "building_name": building_name,
        }
        if locality_en:
            cleaned_station["locality_en"] = locality_en
        cleaned.append(cleaned_station)

    for station in cleaned:
        normalized_locality = normalize(station["locality"])
        count = locality_counts.get(normalized_locality, 0)
        if count > 1:
            duplicate_localities_in_upload[station["locality"]] = count

    ambiguity_report: Dict[str, list] = {}
    if parliamentary_constituency and assembly and other_rows is not None:
        ambiguity_report = _collect_constituency_ambiguities(
            parliamentary_constituency,
            assembly,
            cleaned,
            other_rows,
        )

    report = {
        "rows_received": len(list(stations or [])) if not isinstance(stations, list) else len(stations),
        "rows_saved": len(cleaned),
        "meta_rows_removed": len(removed_meta_rows),
        "meta_row_samples": removed_meta_rows[:20],
        "duplicate_localities_in_upload": duplicate_localities_in_upload,
        "ambiguous_localities_against_constituency": ambiguity_report,
        "missing_locality_en_count": sum(1 for station in cleaned if not station.get("locality_en")),
        "missing_locality_en_samples": missing_locality_en_samples[:20],
    }
    return cleaned, report

def get_keywords(text: str) -> set:
    """Get significant words >= 4 chars, excluding generic location/complaint terms."""
    words = normalize(text).split()
    stopwords = {
        # English generic
        "road", "street", "near", "opp", "opposite", "behind", "front", 
        "main", "cross", "lane", "area", "colony", "city", 
        "town", "village", "taluk", "district", "state", "ward", "zone",
        "problem", "issue", "water", "logging", "broken", "bad",
        "east", "west", "north", "south", "station", "nagar", "chowk",
        "market", "park", "garden", "society", "sector", "block", "camp",
        "gate", "bridge", "school", "college", "hospital", "temple",
        "masjid", "church", "railway", "bus", "stop", "circle", "square",
        # Indian location generic
        "bazar", "bazaar", "peth", "pet", "galli", "gali", "wadi", "wada",
        "gaon", "goan", "pada", "pura", "pur", "abad", "ghat", "khurd",
        "budruk", "tarf", "road", "marg", "path", "math", "devi",
        "maharaj", "govt", "government", "primary", "high", "english",
        "medium", "kannada", "marathi", "urdu", "hindi",
        "building", "room", "hall", "office", "depot", "vaccine",
        "number", "polling", "booth", "average", "voters",
        "total", "part", "page", "list",
        # Complaint language (Hindi/Marathi/Kannada/English)
        "classroom", "toilet", "rasta", "kharab", "nahi", "aahe",
        "milto", "madhe", "teacher", "tutla", "tutli", "band",
        "paani", "supply", "drain", "khade", "footpath", "light",
        "phone", "call", "please", "help", "urgent", "request",
        "complaint", "regarding", "about", "from", "this", "that",
        "very", "much", "also", "here", "there", "where", "when",
    }
    return {w for w in words if len(w) >= 4 and w not in stopwords}

def similarity_score(a: str, b: str) -> float:
    """Returns a score between 0 and 100 indicating how similar two strings are."""
    return SequenceMatcher(None, a, b).ratio() * 100

# --- LOADER ---
def load_geography_index() -> bool:
    global _geography_index

    logger.debug(f"INDEXING GEOGRAPHY FROM: {GEOGRAPHY_BASE_PATH}")
    _init_empty_index()
    files_loaded = 0

    sources = []
    try:
        from sansadx_backend.db import get_all_geography_data
        db_rows = get_all_geography_data()
        if db_rows:
            for row in db_rows:
                sources.append(
                    (
                        row["parliamentary_constituency"],
                        row["assembly"],
                        row["stations"],
                    )
                )
    except Exception:
        pass

    if not sources and GEOGRAPHY_BASE_PATH:
        for parl_dir in GEOGRAPHY_BASE_PATH.iterdir():
            if not parl_dir.is_dir():
                continue
            parl_name = parl_dir.name
            for json_file in parl_dir.glob("*.json"):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        stations = json.load(f)
                except Exception:
                    continue
                sources.append((parl_name, json_file.stem, stations))

    for parl_name, assembly, stations in sources:
        if assembly not in _geography_index["assemblies"]:
            _geography_index["assemblies"][assembly] = {"parl": parl_name, "entries": []}

        for s in stations:
            raw_loc = s.get("locality", "").replace("\n", " ").strip()
            raw_bldg = s.get("building_name", "").replace("\n", " ").strip()
            station = str(s.get("station_number", "")).strip()

            norm_loc = normalize(raw_loc)
            raw_loc_en = s.get("locality_en", "").replace("\n", " ").strip()
            if not norm_loc or _is_meta_locality(raw_loc):
                continue

            match_forms = _generated_alias_forms(s, parl_name)
            spaceless_match_forms = _spaceless_forms(match_forms)
            keywords = set()
            for form in match_forms:
                keywords |= get_keywords(form)
            keywords |= get_keywords(raw_bldg)

            _geography_index["assemblies"][assembly]["entries"].append({
                "orig_name": raw_loc,
                "match_forms": match_forms,
                "spaceless_match_forms": spaceless_match_forms,
                "station": station,
                "keywords": keywords,
            })
            _register_entry_ambiguities(parl_name, assembly, match_forms)
            _register_entry_ambiguities(parl_name, assembly, spaceless_match_forms)
        files_loaded += 1
        logger.debug(f"   Indexed {assembly}: {len(stations)} locations")

    _geography_index["loaded"] = True
    return files_loaded > 0

# --- RESOLVER ---
def resolve_location(text: str, scope_parliamentary: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if not text: return {"location_resolved": False}
    if not _geography_index["loaded"]: load_geography_index()

    query_forms = _build_match_forms(text)
    if not query_forms:
        return {"location_resolved": False}

    clean_text = max(query_forms, key=len)
    spaceless_query_forms = _spaceless_forms(query_forms)
    spaceless_query_phrase_forms = _spaceless_phrase_forms(query_forms)
    user_keywords = set()
    for form in query_forms:
        user_keywords |= get_keywords(form)
    
    logger.debug(f"RESOLVING: '{clean_text}' (tenant={tenant_id})")

    # 1. TENANT-SPECIFIC OVERRIDES (from tenant_overrides.json)
    if tenant_id is not None:
        tenant_aliases = _load_tenant_geo_aliases(int(tenant_id))
        for alias_key, payload in tenant_aliases.items():
            alias_forms = _build_match_forms(alias_key)
            if not alias_forms:
                continue
            if alias_forms & query_forms:
                return {
                    "location_resolved": True,
                    "assembly_constituency": payload["assembly"],
                    "matched_value": _display_location_name(payload["display"]),
                    "confidence": "db_alias_exact",
                }
            for alias_form in alias_forms:
                if len(alias_form) >= 5 and any(re.search(r'\b' + re.escape(alias_form) + r'\b', qf) for qf in query_forms):
                    return {
                        "location_resolved": True,
                        "assembly_constituency": payload["assembly"],
                        "matched_value": _display_location_name(payload["display"]),
                        "confidence": "db_alias_boundary",
                    }

        tenant_overrides = _load_tenant_overrides(tenant_id)
        for k, v in tenant_overrides.items():
            if k.lower() in clean_text:
                logger.debug(f"   OVERRIDE (tenant {tenant_id}): {k} -> {v}")
                return {"location_resolved": True, "assembly_constituency": v, "matched_value": k.title(), "confidence": "god_mode"}

    candidates = []

    for assembly, data in _geography_index["assemblies"].items():
        if scope_parliamentary and normalize(data["parl"]) != normalize(scope_parliamentary): continue

        for entry in data["entries"]:
            score = 0
            match_type = "none"
            matched_name = entry["orig_name"]
            entry_forms = entry.get("match_forms", set())
            entry_spaceless_forms = entry.get("spaceless_match_forms", set())
            entry_name = max(entry_forms, key=len) if entry_forms else ""

            # A. EXACT MATCH — highest priority (full string match)
            exact_forms = entry_forms & query_forms
            if exact_forms:
                matched_form = max(exact_forms, key=len)
                score = 150 + len(matched_form)
                match_type = "exact_full"
                matched_name = matched_form

            # B. WORD BOUNDARY MATCH — entry name appears as complete word(s) in user text
            # Prevents "hosur" matching "gilihosur" or "chandanhosur"
            elif entry_forms:
                boundary_matches = []
                for entry_form in entry_forms:
                    if len(entry_form) < 4:
                        continue
                    word_pattern = r'\b' + re.escape(entry_form) + r'\b'
                    if any(re.search(word_pattern, query_form) for query_form in query_forms):
                        boundary_matches.append(entry_form)
                if boundary_matches:
                    matched_form = max(boundary_matches, key=len)
                    score = 120 + len(matched_form)
                    match_type = "word_boundary"
                    matched_name = matched_form

            # C. EXACT SUBSTRING — entry name contained in user text (min 5 chars)
            # Score based on length to prefer longer/more specific matches
            if score == 0 and entry_forms:
                substring_matches = []
                for entry_form in entry_forms:
                    if len(entry_form) < 5:
                        continue
                    if any(entry_form in query_form for query_form in query_forms):
                        substring_matches.append(entry_form)
                if substring_matches:
                    matched_form = max(substring_matches, key=len)
                    score = 100 + len(matched_form)
                    match_type = "exact_substring"
                    matched_name = matched_form

            # E. SPACELESS MATCH — original (Fixes "Shahunagar" vs "Shahu Nagar")
            # Only if the spaceless version is significantly long (avoid false positives)
            if score == 0 and entry_spaceless_forms:
                spaceless_matches = []
                for entry_form in entry_spaceless_forms:
                    if len(entry_form) < 6:
                        continue
                    if any(entry_form in query_form for query_form in spaceless_query_forms):
                        spaceless_matches.append(entry_form)
                if spaceless_matches:
                    matched_form = max(spaceless_matches, key=len)
                    score = 112 + len(matched_form)
                    match_type = "spaceless"
                    for form in entry_forms:
                        if form.replace(" ", "") == matched_form:
                            matched_name = form
                            break

            # F. FUZZY SPACELESS PHRASE MATCH — for voice-note drift such as
            # "shanti baswad" vs indexed "Santibastawad". This is restricted
            # to adjacent multi-word user phrases and longer indexed names.
            if entry_spaceless_forms and spaceless_query_phrase_forms:
                best_phrase_match = None
                best_phrase_score = 0.0
                for query_phrase in spaceless_query_phrase_forms:
                    for entry_form in entry_spaceless_forms:
                        if len(entry_form) < 8:
                            continue
                        if not (0.75 <= len(query_phrase) / len(entry_form) <= 1.25):
                            continue
                        sim = similarity_score(query_phrase, entry_form)
                        if sim >= 94 and sim > best_phrase_score:
                            best_phrase_score = sim
                            best_phrase_match = entry_form
                if best_phrase_match:
                    phrase_score = 130 + best_phrase_score / 10
                    if phrase_score > score:
                        score = phrase_score
                        match_type = f"fuzzy_phrase ({best_phrase_score:.1f})"
                        for form in entry_forms:
                            if form.replace(" ", "") == best_phrase_match:
                                matched_name = form
                                break

            # G. FUZZY KEYWORD MATCH — STRICT (95% similarity, min 6 char keywords)
            # Only used as last resort to catch typos like "Tilkwadi" vs "Tilakwadi"
            if score == 0:
                for uk in user_keywords:
                    if len(uk) < 6: continue  # Increased from 5 to 6
                    for dk in entry["keywords"]:
                        if len(dk) < 6: continue  # Increased from 5 to 6
                        # Only consider if lengths are similar (±25%)
                        if not (0.75 <= len(uk)/len(dk) <= 1.25):
                            continue
                        sim = similarity_score(uk, dk)
                        if sim > 95:  # Increased from 92 to 95
                            score = sim
                            match_type = f"fuzzy_strict ({uk}~{dk})"
                            matched_name = dk
                            break
                    if score > 0:
                        break

            # Only accept matches with score > 70 (raised threshold)
            if score > 70:
                candidates.append({
                    "assembly": assembly,
                    "parl": data["parl"],
                    "name": entry["orig_name"],
                    "matched_name": _display_location_name(matched_name),
                    "score": score,
                    "type": match_type
                })

    if not candidates:
        return {"location_resolved": False}

    candidates.sort(key=lambda x: (-x["score"], len(x["name"])))
    winner = candidates[0]
    top_score = winner["score"]
    top_candidates = [c for c in candidates if c["score"] == top_score]
    top_assemblies = sorted({candidate["assembly"] for candidate in top_candidates})
    if len(top_assemblies) > 1:
        return {
            "location_resolved": False,
            "reason": "ambiguous_match",
            "ambiguous_assemblies": top_assemblies,
            "matched_value": winner["matched_name"],
            "parliamentary_constituency": winner["parl"],
        }

    logger.debug(f"   WINNER: {winner['name']} ({winner['assembly']}) - Score: {winner['score']:.1f} [{winner['type']}]")
    
    return {
        "location_resolved": True,
        "assembly_constituency": winner["assembly"],
        "parliamentary_constituency": winner["parl"],
        "matched_value": winner["matched_name"],
        "confidence": "high"
    }

# --- WRAPPERS ---
def _get_tenant_constituency(tenant_id):
    """Look up the parliamentary constituency for a given tenant_id."""
    if not tenant_id:
        return None
    try:
        from sansadx_backend.db import get_tenant_constituency
        constituency = get_tenant_constituency(tenant_id)
        if constituency:
            return constituency
    except Exception:
        pass
    try:
        # Try tenant_overrides.json first
        override_paths = [
            PROJECT_ROOT / "tenant_overrides.json",
            Path("tenant_overrides.json").resolve(),
        ]
        for op in override_paths:
            if op.exists():
                with open(op, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # Check if constituency is stored in overrides
                tenant_data = data.get("tenants", {}).get(str(tenant_id), {})
                if tenant_data.get("constituency"):
                    return tenant_data["constituency"]
    except Exception:
        pass
    
    # Fallback: look up from DB
    try:
        from sansadx_backend.db import SessionLocal, Tenant
        db = SessionLocal()
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
        if tenant and tenant.constituency:
            db.close()
            return tenant.constituency
        db.close()
    except Exception:
        pass
    
    return None

def enrich_grievance_with_location(grievance: Dict, tenant_id: Optional[int] = None) -> Dict:
    text = grievance.get("raw_message") or ""
    # Auto-scope by tenant's parliamentary constituency
    scope = _get_tenant_constituency(tenant_id) if tenant_id else None
    logger.info(f"Enriching grievance for tenant={tenant_id}, scope={scope}")
    res = resolve_location(text, scope_parliamentary=scope, tenant_id=tenant_id)
    grievance["geography"] = res
    return grievance

def resolve_constituency(text: str, tenant_id: Optional[int] = None):
    """
    Wrapper used by main.py WhatsApp webhook.
    Returns (matched_value, assembly_constituency) or (None, None).
    """
    scope = _get_tenant_constituency(tenant_id) if tenant_id else None
    result = resolve_location(text, scope_parliamentary=scope, tenant_id=tenant_id)
    if result.get("location_resolved"):
        return result.get("matched_value"), result.get("assembly_constituency")
    return None, None


def get_index_stats() -> Dict[str, int]:
    ambiguity_count = sum(
        1 for parl_map in _geography_index.get("ambiguities", {}).values()
        for assemblies in parl_map.values()
        if len(assemblies) > 1
    )
    return {"loaded": _geography_index["loaded"], "assemblies": len(_geography_index["assemblies"]), "ambiguities": ambiguity_count}

def reload_index():
    _init_empty_index()
    return load_geography_index()

# ==========================================
# AUTO-GENERATE OVERRIDES FROM GEOGRAPHY DATA
# ==========================================
def auto_generate_overrides():
    """
    Scans persisted geography data, extracts locality→assembly mappings, and
    writes them to the DB as geo_override rows.
    """
    try:
        from sansadx_backend.db import SessionLocal, Tenant, get_all_geography_data
        db = SessionLocal()
        tenant_rows = db.query(Tenant).all()
        constituency_to_tenant = {
            t.constituency: t.id
            for t in tenant_rows
            if t.constituency and t.constituency != "System"
        }
        db.close()
        geography_rows = get_all_geography_data()
    except Exception as e:
        logger.warning(f"Could not load geography data from DB: {e}")
        geography_rows = []

    if not geography_rows and GEOGRAPHY_BASE_PATH and GEOGRAPHY_BASE_PATH.exists():
        for parl_dir in sorted(GEOGRAPHY_BASE_PATH.iterdir()):
            if not parl_dir.is_dir():
                continue
            for json_file in sorted(parl_dir.glob("*.json")):
                try:
                    with open(json_file, "r", encoding="utf-8") as f:
                        stations = json.load(f)
                except Exception:
                    continue
                geography_rows.append({
                    "tenant_id": constituency_to_tenant.get(parl_dir.name),
                    "parliamentary_constituency": parl_dir.name,
                    "assembly": json_file.stem,
                    "stations": stations if isinstance(stations, list) else [],
                })

    if not geography_rows:
        logger.warning("No geography data available for override generation")
        return {"error": "No geography data found"}

    stats = {}
    total_written = 0

    grouped_rows = {}
    for row in geography_rows:
        parl_name = row["parliamentary_constituency"]
        tenant_id = row.get("tenant_id") or constituency_to_tenant.get(parl_name)
        if not tenant_id:
            logger.info(f"No tenant found for constituency '{parl_name}', skipping override generation")
            continue
        grouped_rows.setdefault((parl_name, tenant_id), []).append(row)

    for (parl_name, tenant_id), rows in grouped_rows.items():
        overrides_map = {}
        alias_payloads = {}
        ambiguous_localities: Dict[str, Set[str]] = {}
        for row in rows:
            assembly_name = row["assembly"]
            stations = row.get("stations") or []
            for station in stations:
                locality = station.get("locality", "").replace("\n", " ").strip()
                if not locality or len(locality) < 3 or _is_meta_locality(locality):
                    continue
                display = _display_location_name(locality)
                station_alias_forms = _generated_alias_forms(station, parl_name)
                for key in sorted(station_alias_forms or {normalize(locality)}):
                    if not key:
                        continue
                    if key in overrides_map and overrides_map[key] != assembly_name:
                        ambiguous_localities.setdefault(key, {overrides_map[key]}).add(assembly_name)
                        overrides_map.pop(key, None)
                        alias_payloads.pop(key, None)
                        continue
                    if key in ambiguous_localities:
                        ambiguous_localities[key].add(assembly_name)
                        continue
                    if key not in overrides_map:
                        overrides_map[key] = assembly_name
                        alias_payloads[key] = {
                            "assembly": assembly_name,
                            "display": display,
                            "canonical_locality": locality,
                            "source": "geography_data",
                        }

        try:
            from sansadx_backend.db import SessionLocal as SL, TenantOverride
            from sqlalchemy import text as sa_text
            db = SL()
            try:
                db.execute(
                    sa_text("DELETE FROM tenant_overrides WHERE tenant_id = :tid AND override_type IN ('geo_override', 'geo_alias')"),
                    {"tid": tenant_id}
                )
                db.commit()
                for loc_key, assembly_val in overrides_map.items():
                    override = TenantOverride(
                        tenant_id=tenant_id,
                        override_type="geo_override",
                        key=loc_key,
                        value=assembly_val,
                    )
                    db.add(override)
                    db.add(TenantOverride(
                        tenant_id=tenant_id,
                        override_type="geo_alias",
                        key=loc_key,
                        value=json.dumps(alias_payloads.get(loc_key) or {
                            "assembly": assembly_val,
                            "display": loc_key,
                            "source": "geography_data",
                        }),
                    ))
                
                db.commit()
                total_written += len(overrides_map)
                logger.info(f"Wrote {len(overrides_map)} geo_overrides for tenant {tenant_id} ({parl_name})")
            finally:
                db.close()
        except Exception as e:
            logger.error(f"Failed to write geo_overrides to DB for {parl_name}: {e}")
        
        stats[parl_name] = {
            "tenant_id": tenant_id,
            "overrides_written": len(overrides_map),
            "ambiguous_localities_skipped": {
                locality: sorted(assemblies)
                for locality, assemblies in sorted(ambiguous_localities.items())
            },
        }

    return {"success": True, "total_written": total_written, "stats": stats}
