"""
Geography Resolver (MULTI-TENANT) — Pan-India Edition
1. Checks tenant-specific DB overrides (per tenant_id).
2. Filters junk polling-sheet/meta rows before indexing.
3. Exact/alias substring match against geography index.
4. Spaceless Match (Fixes "Shahunagar" vs "Shahu Nagar").
5. Fuzzy Typos Match (Fixes "Tilkwadi" vs "Tilakwadi").

Transliteration covers all 22 scheduled + major Indian scripts with correct
inherent-vowel handling (all Brahmi-derived scripts encode an implicit 'a'
after every consonant unless suppressed by a virama/halant or replaced by a
matra). Supported: Devanagari, Bengali/Assamese, Gurmukhi/Punjabi, Gujarati,
Odia, Tamil, Telugu, Kannada, Malayalam, Arabic/Urdu.
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
# PAN-INDIA TRANSLITERATION
# 22 scheduled languages + major scripts.
# Each consonant map uses bare letters (no inherent 'a'); the function
# _insert_inherent_vowels() restores the implicit 'a' between consecutive
# consonants after block-level substitution is complete.
# ==========================================

# --- DEVANAGARI U+0900-U+097F ---
# Hindi, Marathi, Sanskrit, Konkani, Bodo, Dogri, Maithili, Nepali
_DEVA_MAP = {
    # Multi-char conjuncts / nukta composites (must come first)
    '\u0915\u094D\u0937': 'ksh', '\u091C\u094D\u091E': 'gya',  # क्ष, ज्ञ
    '\u0905\u0902': 'an',   # अं
    '\u0921\u093C': 'r',    # ड़
    '\u0922\u093C': 'rh',   # ढ़
    '\u091C\u093C': 'z',    # ज़
    '\u092B\u093C': 'f',    # फ़
    '\u0917\u093C': 'g',    # ग़
    '\u0916\u093C': 'kh',   # ख़
    # Independent vowels
    '\u0905': 'a',  '\u0906': 'aa', '\u0907': 'i',  '\u0908': 'ee',
    '\u0909': 'u',  '\u090A': 'oo', '\u090F': 'e',  '\u0910': 'ai',
    '\u0913': 'o',  '\u0914': 'au', '\u090B': 'ri', '\u090C': 'l',
    '\u090D': 'e',  '\u090E': 'e',  '\u0912': 'o',
    # Consonants (no inherent 'a' — _insert_inherent_vowels adds it)
    '\u0915': 'k',  '\u0916': 'kh', '\u0917': 'g',  '\u0918': 'gh', '\u0919': 'ng',
    '\u091A': 'ch', '\u091B': 'chh','\u091C': 'j',  '\u091D': 'jh', '\u091E': 'n',
    '\u091F': 't',  '\u0920': 'th', '\u0921': 'd',  '\u0922': 'dh', '\u0923': 'n',
    '\u0924': 't',  '\u0925': 'th', '\u0926': 'd',  '\u0927': 'dh', '\u0928': 'n',
    '\u092A': 'p',  '\u092B': 'ph', '\u092C': 'b',  '\u092D': 'bh', '\u092E': 'm',
    '\u092F': 'y',  '\u0930': 'r',  '\u0932': 'l',  '\u0935': 'v',
    '\u0936': 'sh', '\u0937': 'sh', '\u0938': 's',  '\u0939': 'h',
    '\u0933': 'l',  '\u0934': 'l',
    # Matras (vowel signs — replace inherent 'a')
    '\u093E': 'a',  '\u093F': 'i',  '\u0940': 'ee', '\u0941': 'u',  '\u0942': 'oo',
    '\u0947': 'e',  '\u0948': 'ai', '\u094B': 'o',  '\u094C': 'au', '\u0943': 'ri',
    '\u0944': 'ri', '\u0945': 'e',  '\u0946': 'e',  '\u094A': 'o',
    # Anusvara / chandrabindu / visarga / halant (virama)
    '\u0902': 'n',  '\u0901': 'n',  '\u0903': 'h',  '\u094D': '',
    # Digits
    '\u0966': '0', '\u0967': '1', '\u0968': '2', '\u0969': '3', '\u096A': '4',
    '\u096B': '5', '\u096C': '6', '\u096D': '7', '\u096E': '8', '\u096F': '9',
}
_DEVA_RE = re.compile(r'[\u0900-\u097F]')

# --- BENGALI / ASSAMESE U+0980-U+09FF ---
_BENGALI_MAP = {
    '\u0985': 'a',  '\u0986': 'aa', '\u0987': 'i',  '\u0988': 'ee',
    '\u0989': 'u',  '\u098A': 'u',  '\u098B': 'ri', '\u098C': 'l',
    '\u098F': 'e',  '\u0990': 'oi', '\u0993': 'o',  '\u0994': 'ou',
    '\u0995': 'k',  '\u0996': 'kh', '\u0997': 'g',  '\u0998': 'gh', '\u0999': 'ng',
    '\u099A': 'ch', '\u099B': 'chh','\u099C': 'j',  '\u099D': 'jh', '\u099E': 'n',
    '\u099F': 't',  '\u09A0': 'th', '\u09A1': 'd',  '\u09A2': 'dh', '\u09A3': 'n',
    '\u09A4': 't',  '\u09A5': 'th', '\u09A6': 'd',  '\u09A7': 'dh', '\u09A8': 'n',
    '\u09AA': 'p',  '\u09AB': 'ph', '\u09AC': 'b',  '\u09AD': 'bh', '\u09AE': 'm',
    '\u09AF': 'j',  '\u09B0': 'r',  '\u09B2': 'l',
    '\u09B6': 'sh', '\u09B7': 'sh', '\u09B8': 's',  '\u09B9': 'h',
    '\u09DC': 'r',  '\u09DD': 'rh', '\u09DF': 'y',  '\u09CE': 't',
    # Matras
    '\u09BE': 'a',  '\u09BF': 'i',  '\u09C0': 'ee', '\u09C1': 'u',  '\u09C2': 'oo',
    '\u09C3': 'ri', '\u09C7': 'e',  '\u09C8': 'oi', '\u09CB': 'o',  '\u09CC': 'ou',
    '\u09C4': 'ri',
    '\u09BC': '',   # nukta
    '\u0982': 'n',  '\u0983': 'h',  '\u09CD': '',   # anusvara / visarga / hasanta
    '\u09E6': '0',  '\u09E7': '1',  '\u09E8': '2',  '\u09E9': '3',  '\u09EA': '4',
    '\u09EB': '5',  '\u09EC': '6',  '\u09ED': '7',  '\u09EE': '8',  '\u09EF': '9',
}
_BENGALI_RE = re.compile(r'[\u0980-\u09FF]')

# --- GURMUKHI / PUNJABI U+0A00-U+0A7F ---
_GURMUKHI_MAP = {
    '\u0A05': 'a',  '\u0A06': 'aa', '\u0A07': 'i',  '\u0A08': 'ee',
    '\u0A09': 'u',  '\u0A0A': 'oo', '\u0A0F': 'e',  '\u0A10': 'ai',
    '\u0A13': 'o',  '\u0A14': 'au',
    '\u0A15': 'k',  '\u0A16': 'kh', '\u0A17': 'g',  '\u0A18': 'gh', '\u0A19': 'ng',
    '\u0A1A': 'ch', '\u0A1B': 'chh','\u0A1C': 'j',  '\u0A1D': 'jh', '\u0A1E': 'n',
    '\u0A1F': 't',  '\u0A20': 'th', '\u0A21': 'd',  '\u0A22': 'dh', '\u0A23': 'n',
    '\u0A24': 't',  '\u0A25': 'th', '\u0A26': 'd',  '\u0A27': 'dh', '\u0A28': 'n',
    '\u0A2A': 'p',  '\u0A2B': 'ph', '\u0A2C': 'b',  '\u0A2D': 'bh', '\u0A2E': 'm',
    '\u0A2F': 'y',  '\u0A30': 'r',  '\u0A32': 'l',  '\u0A35': 'v',
    '\u0A38': 's',  '\u0A39': 'h',  '\u0A5C': 'r',
    # Nukta forms: sha, kha, gha, za, fa, lla
    '\u0A36': 'sh', '\u0A59': 'kh', '\u0A5A': 'g',  '\u0A5B': 'z',  '\u0A5E': 'f',
    '\u0A33': 'l',
    # Matras
    '\u0A3E': 'a',  '\u0A3F': 'i',  '\u0A40': 'ee', '\u0A41': 'u',  '\u0A42': 'oo',
    '\u0A47': 'e',  '\u0A48': 'ai', '\u0A4B': 'o',  '\u0A4C': 'au',
    '\u0A70': 'n',  '\u0A71': '',   # tippi / addak
    '\u0A02': 'n',  '\u0A4D': '',   # bindi / virama
    '\u0A66': '0',  '\u0A67': '1',  '\u0A68': '2',  '\u0A69': '3',  '\u0A6A': '4',
    '\u0A6B': '5',  '\u0A6C': '6',  '\u0A6D': '7',  '\u0A6E': '8',  '\u0A6F': '9',
}
_GURMUKHI_RE = re.compile(r'[\u0A00-\u0A7F]')

# --- GUJARATI U+0A80-U+0AFF ---
_GUJARATI_MAP = {
    '\u0A95\u0ACD\u0AB7': 'ksh',  # ક્ષ
    '\u0A85': 'a',  '\u0A86': 'aa', '\u0A87': 'i',  '\u0A88': 'ee',
    '\u0A89': 'u',  '\u0A8A': 'oo', '\u0A8B': 'ri', '\u0A8F': 'e',
    '\u0A90': 'ai', '\u0A93': 'o',  '\u0A94': 'au',
    '\u0A95': 'k',  '\u0A96': 'kh', '\u0A97': 'g',  '\u0A98': 'gh', '\u0A99': 'ng',
    '\u0A9A': 'ch', '\u0A9B': 'chh','\u0A9C': 'j',  '\u0A9D': 'jh', '\u0A9E': 'n',
    '\u0A9F': 't',  '\u0AA0': 'th', '\u0AA1': 'd',  '\u0AA2': 'dh', '\u0AA3': 'n',
    '\u0AA4': 't',  '\u0AA5': 'th', '\u0AA6': 'd',  '\u0AA7': 'dh', '\u0AA8': 'n',
    '\u0AAA': 'p',  '\u0AAB': 'ph', '\u0AAC': 'b',  '\u0AAD': 'bh', '\u0AAE': 'm',
    '\u0AAF': 'y',  '\u0AB0': 'r',  '\u0AB2': 'l',  '\u0AB3': 'l',  '\u0AB5': 'v',
    '\u0AB6': 'sh', '\u0AB7': 'sh', '\u0AB8': 's',  '\u0AB9': 'h',
    # Matras
    '\u0ABE': 'a',  '\u0ABF': 'i',  '\u0AC0': 'ee', '\u0AC1': 'u',  '\u0AC2': 'oo',
    '\u0AC3': 'ri', '\u0AC7': 'e',  '\u0AC8': 'ai', '\u0ACB': 'o',  '\u0ACC': 'au',
    '\u0A82': 'n',  '\u0A83': 'h',  '\u0ACD': '',
    '\u0AE6': '0',  '\u0AE7': '1',  '\u0AE8': '2',  '\u0AE9': '3',  '\u0AEA': '4',
    '\u0AEB': '5',  '\u0AEC': '6',  '\u0AED': '7',  '\u0AEE': '8',  '\u0AEF': '9',
}
_GUJARATI_RE = re.compile(r'[\u0A80-\u0AFF]')

# --- ODIA / ORIYA U+0B00-U+0B7F ---
_ODIA_MAP = {
    '\u0B05': 'a',  '\u0B06': 'aa', '\u0B07': 'i',  '\u0B08': 'ee',
    '\u0B09': 'u',  '\u0B0A': 'oo', '\u0B0B': 'ri', '\u0B0F': 'e',
    '\u0B10': 'ai', '\u0B13': 'o',  '\u0B14': 'au',
    '\u0B15': 'k',  '\u0B16': 'kh', '\u0B17': 'g',  '\u0B18': 'gh', '\u0B19': 'ng',
    '\u0B1A': 'ch', '\u0B1B': 'chh','\u0B1C': 'j',  '\u0B1D': 'jh', '\u0B1E': 'n',
    '\u0B1F': 't',  '\u0B20': 'th', '\u0B21': 'd',  '\u0B22': 'dh', '\u0B23': 'n',
    '\u0B24': 't',  '\u0B25': 'th', '\u0B26': 'd',  '\u0B27': 'dh', '\u0B28': 'n',
    '\u0B2A': 'p',  '\u0B2B': 'ph', '\u0B2C': 'b',  '\u0B2D': 'bh', '\u0B2E': 'm',
    '\u0B2F': 'j',  '\u0B30': 'r',  '\u0B32': 'l',  '\u0B33': 'l',
    '\u0B35': 'v',  '\u0B36': 'sh', '\u0B37': 'sh', '\u0B38': 's',  '\u0B39': 'h',
    '\u0B5C': 'r',  '\u0B5D': 'rh', '\u0B5F': 'y',
    # Matras
    '\u0B3E': 'a',  '\u0B3F': 'i',  '\u0B40': 'ee', '\u0B41': 'u',  '\u0B42': 'oo',
    '\u0B43': 'ri', '\u0B47': 'e',  '\u0B48': 'ai', '\u0B4B': 'o',  '\u0B4C': 'au',
    '\u0B01': 'n',  '\u0B02': 'n',  '\u0B03': 'h',  '\u0B4D': '',
    '\u0B66': '0',  '\u0B67': '1',  '\u0B68': '2',  '\u0B69': '3',  '\u0B6A': '4',
    '\u0B6B': '5',  '\u0B6C': '6',  '\u0B6D': '7',  '\u0B6E': '8',  '\u0B6F': '9',
}
_ODIA_RE = re.compile(r'[\u0B00-\u0B7F]')

# --- TAMIL U+0B80-U+0BFF ---
# Tamil has 18 consonants; same letter represents multiple phonemes by position.
_TAMIL_MAP = {
    '\u0B85': 'a',  '\u0B86': 'aa', '\u0B87': 'i',  '\u0B88': 'ee',
    '\u0B89': 'u',  '\u0B8A': 'oo', '\u0B8E': 'e',  '\u0B8F': 'e',
    '\u0B90': 'ai', '\u0B92': 'o',  '\u0B93': 'o',  '\u0B94': 'au',
    '\u0B95': 'k',  '\u0B99': 'ng', '\u0B9A': 'ch', '\u0B9C': 'j',  '\u0B9E': 'n',
    '\u0B9F': 't',  '\u0BA3': 'n',  '\u0BA4': 'th', '\u0BA8': 'n',  '\u0BA9': 'n',
    '\u0BAA': 'p',  '\u0BAE': 'm',  '\u0BAF': 'y',  '\u0BB0': 'r',  '\u0BB1': 'r',
    '\u0BB2': 'l',  '\u0BB3': 'l',  '\u0BB4': 'zh', '\u0BB5': 'v',
    '\u0BB6': 'sh', '\u0BB7': 'sh', '\u0BB8': 's',  '\u0BB9': 'h',
    '\u0B83': 'h',  # aytham
    # Matras
    '\u0BBE': 'a',  '\u0BBF': 'i',  '\u0BC0': 'ee', '\u0BC1': 'u',  '\u0BC2': 'oo',
    '\u0BC6': 'e',  '\u0BC7': 'e',  '\u0BC8': 'ai', '\u0BCA': 'o',  '\u0BCB': 'o',
    '\u0BCC': 'au', '\u0B82': 'n',  '\u0BCD': '',
    '\u0BE6': '0',  '\u0BE7': '1',  '\u0BE8': '2',  '\u0BE9': '3',  '\u0BEA': '4',
    '\u0BEB': '5',  '\u0BEC': '6',  '\u0BED': '7',  '\u0BEE': '8',  '\u0BEF': '9',
}
_TAMIL_RE = re.compile(r'[\u0B80-\u0BFF]')

# --- TELUGU U+0C00-U+0C7F ---
_TELUGU_MAP = {
    '\u0C05': 'a',  '\u0C06': 'aa', '\u0C07': 'i',  '\u0C08': 'ee',
    '\u0C09': 'u',  '\u0C0A': 'oo', '\u0C0B': 'ri', '\u0C0E': 'e',
    '\u0C0F': 'e',  '\u0C10': 'ai', '\u0C12': 'o',  '\u0C13': 'o',  '\u0C14': 'au',
    '\u0C15': 'k',  '\u0C16': 'kh', '\u0C17': 'g',  '\u0C18': 'gh', '\u0C19': 'ng',
    '\u0C1A': 'ch', '\u0C1B': 'chh','\u0C1C': 'j',  '\u0C1D': 'jh', '\u0C1E': 'n',
    '\u0C1F': 't',  '\u0C20': 'th', '\u0C21': 'd',  '\u0C22': 'dh', '\u0C23': 'n',
    '\u0C24': 't',  '\u0C25': 'th', '\u0C26': 'd',  '\u0C27': 'dh', '\u0C28': 'n',
    '\u0C2A': 'p',  '\u0C2B': 'ph', '\u0C2C': 'b',  '\u0C2D': 'bh', '\u0C2E': 'm',
    '\u0C2F': 'y',  '\u0C30': 'r',  '\u0C31': 'r',  '\u0C32': 'l',  '\u0C33': 'l',
    '\u0C35': 'v',  '\u0C36': 'sh', '\u0C37': 'sh', '\u0C38': 's',  '\u0C39': 'h',
    # Matras
    '\u0C3E': 'a',  '\u0C3F': 'i',  '\u0C40': 'ee', '\u0C41': 'u',  '\u0C42': 'oo',
    '\u0C43': 'ri', '\u0C46': 'e',  '\u0C47': 'e',  '\u0C48': 'ai', '\u0C4A': 'o',
    '\u0C4B': 'o',  '\u0C4C': 'au', '\u0C02': 'n',  '\u0C03': 'h',  '\u0C4D': '',
    '\u0C66': '0',  '\u0C67': '1',  '\u0C68': '2',  '\u0C69': '3',  '\u0C6A': '4',
    '\u0C6B': '5',  '\u0C6C': '6',  '\u0C6D': '7',  '\u0C6E': '8',  '\u0C6F': '9',
}
_TELUGU_RE = re.compile(r'[\u0C00-\u0C7F]')

# --- KANNADA U+0C80-U+0CFF ---
_KANNADA_MAP = {
    '\u0C85': 'a',  '\u0C86': 'aa', '\u0C87': 'i',  '\u0C88': 'ee',
    '\u0C89': 'u',  '\u0C8A': 'oo', '\u0C8B': 'ri', '\u0C8E': 'e',
    '\u0C8F': 'e',  '\u0C90': 'ai', '\u0C92': 'o',  '\u0C93': 'o',  '\u0C94': 'au',
    '\u0C95': 'k',  '\u0C96': 'kh', '\u0C97': 'g',  '\u0C98': 'gh', '\u0C99': 'ng',
    '\u0C9A': 'ch', '\u0C9B': 'chh','\u0C9C': 'j',  '\u0C9D': 'jh', '\u0C9E': 'ny',
    '\u0C9F': 't',  '\u0CA0': 'th', '\u0CA1': 'd',  '\u0CA2': 'dh', '\u0CA3': 'n',
    '\u0CA4': 't',  '\u0CA5': 'th', '\u0CA6': 'd',  '\u0CA7': 'dh', '\u0CA8': 'n',
    '\u0CAA': 'p',  '\u0CAB': 'ph', '\u0CAC': 'b',  '\u0CAD': 'bh', '\u0CAE': 'm',
    '\u0CAF': 'y',  '\u0CB0': 'r',  '\u0CB1': 'r',  '\u0CB2': 'l',  '\u0CB3': 'l',
    '\u0CB5': 'v',  '\u0CB6': 'sh', '\u0CB7': 'sh', '\u0CB8': 's',  '\u0CB9': 'h',
    # Vowel signs
    '\u0CBE': 'a',  '\u0CBF': 'i',  '\u0CC0': 'ee', '\u0CC1': 'u',  '\u0CC2': 'oo',
    '\u0CC3': 'ri', '\u0CC6': 'e',  '\u0CC7': 'e',  '\u0CC8': 'ai', '\u0CCA': 'o',
    '\u0CCB': 'o',  '\u0CCC': 'au', '\u0C82': 'n',  '\u0C83': 'h',  '\u0CCD': '',
    '\u0CE6': '0',  '\u0CE7': '1',  '\u0CE8': '2',  '\u0CE9': '3',  '\u0CEA': '4',
    '\u0CEB': '5',  '\u0CEC': '6',  '\u0CED': '7',  '\u0CEE': '8',  '\u0CEF': '9',
}
_KANNADA_RE = re.compile(r'[\u0C80-\u0CFF]')

# --- MALAYALAM U+0D00-U+0D7F ---
_MALAYALAM_MAP = {
    '\u0D05': 'a',  '\u0D06': 'aa', '\u0D07': 'i',  '\u0D08': 'ee',
    '\u0D09': 'u',  '\u0D0A': 'oo', '\u0D0B': 'ri', '\u0D0E': 'e',
    '\u0D0F': 'e',  '\u0D10': 'ai', '\u0D12': 'o',  '\u0D13': 'o',  '\u0D14': 'au',
    '\u0D15': 'k',  '\u0D16': 'kh', '\u0D17': 'g',  '\u0D18': 'gh', '\u0D19': 'ng',
    '\u0D1A': 'ch', '\u0D1B': 'chh','\u0D1C': 'j',  '\u0D1D': 'jh', '\u0D1E': 'n',
    '\u0D1F': 't',  '\u0D20': 'th', '\u0D21': 'd',  '\u0D22': 'dh', '\u0D23': 'n',
    '\u0D24': 'th', '\u0D25': 'th', '\u0D26': 'd',  '\u0D27': 'dh', '\u0D28': 'n',
    '\u0D2A': 'p',  '\u0D2B': 'ph', '\u0D2C': 'b',  '\u0D2D': 'bh', '\u0D2E': 'm',
    '\u0D2F': 'y',  '\u0D30': 'r',  '\u0D31': 'r',  '\u0D32': 'l',  '\u0D33': 'l',
    '\u0D34': 'zh', '\u0D35': 'v',  '\u0D36': 'sh', '\u0D37': 'sh', '\u0D38': 's',
    '\u0D39': 'h',  '\u0D29': 'n',
    # Chillu letters (pure consonants — no inherent vowel needed)
    '\u0D7A': 'n',  '\u0D7B': 'n',  '\u0D7C': 'r',  '\u0D7D': 'l',  '\u0D7E': 'l',
    '\u0D7F': 'k',
    # Matras
    '\u0D3E': 'a',  '\u0D3F': 'i',  '\u0D40': 'ee', '\u0D41': 'u',  '\u0D42': 'oo',
    '\u0D43': 'ri', '\u0D46': 'e',  '\u0D47': 'e',  '\u0D48': 'ai', '\u0D4A': 'o',
    '\u0D4B': 'o',  '\u0D4C': 'au', '\u0D57': 'au',
    '\u0D02': 'n',  '\u0D03': 'h',  '\u0D4D': '',
    '\u0D66': '0',  '\u0D67': '1',  '\u0D68': '2',  '\u0D69': '3',  '\u0D6A': '4',
    '\u0D6B': '5',  '\u0D6C': '6',  '\u0D6D': '7',  '\u0D6E': '8',  '\u0D6F': '9',
}
_MALAYALAM_RE = re.compile(r'[\u0D00-\u0D7F]')

# --- ARABIC / URDU U+0600-U+06FF ---
# Urdu (also Kashmiri, Sindhi) uses Perso-Arabic. No inherent vowels.
_URDU_MAP = {
    '\u0627': 'a',  '\u0622': 'aa', '\u0628': 'b',  '\u067E': 'p',  '\u062A': 't',
    '\u0679': 't',  '\u062B': 's',  '\u062C': 'j',  '\u0686': 'ch', '\u062D': 'h',
    '\u062E': 'kh', '\u062F': 'd',  '\u0688': 'd',  '\u0630': 'z',  '\u0631': 'r',
    '\u0691': 'r',  '\u0632': 'z',  '\u0698': 'zh', '\u0633': 's',  '\u0634': 'sh',
    '\u0635': 's',  '\u0636': 'z',  '\u0637': 't',  '\u0638': 'z',  '\u0639': 'a',
    '\u063A': 'gh', '\u0641': 'f',  '\u0642': 'q',  '\u06A9': 'k',  '\u06AF': 'g',
    '\u0644': 'l',  '\u0645': 'm',  '\u0646': 'n',  '\u06BA': 'n',  '\u0648': 'w',
    '\u06C1': 'h',  '\u06BE': 'h',  '\u0621': '',   '\u06CC': 'y',  '\u06D2': 'e',
    '\u0626': 'y',  '\u0624': 'w',  '\u0629': 't',  '\u0623': 'a',  '\u0625': 'i',
    '\u0649': 'a',  '\u064A': 'y',
    # Harakat (vowel diacritics — rarely in location names)
    '\u064E': 'a',  '\u064F': 'u',  '\u0650': 'i',  '\u0651': '',   '\u0652': '',
    # Zero-width joiners
    '\u200C': '',   '\u200D': '',
}
_URDU_RE = re.compile(r'[\u0600-\u06FF]')

# --- COMBINED DETECTOR & BLOCK REGEX ---
_ALL_INDIC_PATTERN = (
    r'[\u0900-\u097F'   # Devanagari
    r'\u0980-\u09FF'    # Bengali / Assamese
    r'\u0A00-\u0A7F'    # Gurmukhi / Punjabi
    r'\u0A80-\u0AFF'    # Gujarati
    r'\u0B00-\u0B7F'    # Odia
    r'\u0B80-\u0BFF'    # Tamil
    r'\u0C00-\u0C7F'    # Telugu
    r'\u0C80-\u0CFF'    # Kannada
    r'\u0D00-\u0D7F'    # Malayalam
    r'\u0600-\u06FF]'   # Arabic / Urdu
)
_ALL_INDIC_RE = re.compile(_ALL_INDIC_PATTERN)
_INDIC_BLOCK_RE = re.compile(_ALL_INDIC_PATTERN.rstrip(']') + r']+')

# Ordered list — each map applied per block (multi-char entries pre-sorted below).
_SCRIPT_MAPS_RAW = [
    (_DEVA_MAP,     _DEVA_RE),
    (_BENGALI_MAP,  _BENGALI_RE),
    (_GURMUKHI_MAP, _GURMUKHI_RE),
    (_GUJARATI_MAP, _GUJARATI_RE),
    (_ODIA_MAP,     _ODIA_RE),
    (_TAMIL_MAP,    _TAMIL_RE),
    (_TELUGU_MAP,   _TELUGU_RE),
    (_KANNADA_MAP,  _KANNADA_RE),
    (_MALAYALAM_MAP,_MALAYALAM_RE),
    (_URDU_MAP,     _URDU_RE),
]
_SORTED_SCRIPT_MAPS = [
    (sorted(m.items(), key=lambda x: -len(x[0])), cleanup_re)
    for m, cleanup_re in _SCRIPT_MAPS_RAW
]

# Consonant digraphs and valid clusters that must NOT have 'a' inserted between
# them. Includes aspirated pairs (kh, gh, …), South-Asian romanisation conventions,
# and geminated consonants (tt, nn, …  = geminate, not a missing vowel).
_VALID_CONSONANT_CLUSTERS: frozenset = frozenset({
    # Aspirated consonant digraphs
    'kh', 'gh', 'ng', 'ch', 'jh', 'ny', 'th', 'dh', 'ph', 'bh', 'sh', 'rh', 'zh',
    # Conjunct first-pair tokens
    'ks', 'gy', 'jn',
    # Consonant + liquid / glide
    'tr', 'pr', 'br', 'gr', 'dr', 'kr', 'mr', 'sr', 'vr',
    'ty', 'py', 'by', 'ky', 'my', 'vy', 'sy', 'hy',
    # Nasal + stop clusters — extremely common in Indian names after nasal
    # assimilation (mb, mp, mm, nd, nt, nk, ng already above, nj, ns, nsh):
    'mb', 'mp', 'nd', 'nt', 'nk', 'nj', 'ns', 'nch', 'nc',
    # Geminates (doubled = geminate, no vowel between)
    'bb', 'cc', 'dd', 'ff', 'gg', 'hh', 'jj', 'kk', 'll', 'mm',
    'nn', 'pp', 'rr', 'ss', 'tt', 'vv', 'ww', 'yy', 'zz',
})
_ROMAN_CONSONANTS: frozenset = frozenset('bcdfghjklmnprstvwyz')


def _insert_inherent_vowels(text: str) -> str:
    """
    Restore the inherent 'a' vowel between consecutive consonants that result
    from transliterating a Brahmi-script block.

    In all Brahmi-derived scripts (Devanagari, Bengali, Gurmukhi, Gujarati,
    Odia, Telugu, Kannada, Malayalam, Tamil) every consonant carries an implicit
    'a' unless followed by a virama (mapped to '') or a vowel matra (mapped to
    an explicit vowel). After character substitution, back-to-back Roman
    consonants in the output therefore represent a missing inherent vowel — this
    function inserts 'a' to restore it.

    Only called on text produced from an Indic block (not surrounding English),
    so there is no risk of corrupting existing English words.
    """
    result: list = []
    n = len(text)
    i = 0
    while i < n:
        result.append(text[i])
        if i + 1 < n:
            curr, nxt = text[i], text[i + 1]
            if curr in _ROMAN_CONSONANTS and nxt in _ROMAN_CONSONANTS:
                pair = curr + nxt
                if pair not in _VALID_CONSONANT_CLUSTERS:
                    triple = text[i:i + 3] if i + 2 < n else ''
                    if triple not in {'chh', 'ksh', 'gya', 'jny', 'rhy'}:
                        result.append('a')
        i += 1
    return ''.join(result)


def _apply_script_map(text: str, sorted_entries: list) -> str:
    for src, dst in sorted_entries:
        text = text.replace(src, dst)
    return text


def _is_devanagari(text: str) -> bool:
    return bool(_DEVA_RE.search(text))


def _has_indic_script(text: str) -> bool:
    """Return True if text contains any supported Indian script character."""
    return bool(_ALL_INDIC_RE.search(text))


def _transliterate(text: str) -> str:
    """
    Convert all supported Indian scripts to a simplified Roman form for fuzzy
    matching against casual English spellings of Indian place names.

    Each contiguous Indic block is processed in isolation so inherent-vowel
    insertion never alters surrounding English text. Arabic/Urdu blocks have no
    inherent vowels, so insertion is skipped for those.
    """
    if not _ALL_INDIC_RE.search(text):
        return text

    def _transliterate_block(match: re.Match) -> str:
        block = match.group(0)
        is_arabic = bool(_URDU_RE.search(block))
        for sorted_entries, cleanup_re in _SORTED_SCRIPT_MAPS:
            block = _apply_script_map(block, sorted_entries)
        block = _ALL_INDIC_RE.sub('', block)
        if not is_arabic and block:
            # Nasal assimilation BEFORE inherent-vowel insertion:
            # Anusvara (ं ਂ ং ం ಂ ം etc.) maps to 'n' in all consonant tables,
            # but before bilabials (b/p/m) it assimilates to 'm' in every
            # major Indian language (Sanskrit sandhi rule, universally applied).
            # Must run before _insert_inherent_vowels so 'n' is still adjacent
            # to 'b' (otherwise the inherent-'a' step inserts a vowel between them).
            # e.g. मुंबई: after subs → 'munbee' → assimilate → 'mumbee' → insert
            # inherent vowels → 'mumbee' → canonical 'mumbi' ~ 'mumbai' 91%.
            block = re.sub(r'n([bpm])', r'm\1', block)
            block = _insert_inherent_vowels(block)
        return block

    return _INDIC_BLOCK_RE.sub(_transliterate_block, text).strip()

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
    # ── KANNADA locative: -ನಲ್ಲಿ -ದಲ್ಲಿ etc.
    "inlli", "nlli", "nalli", "inalli", "dalli", "alli", "yalli",
    "inda", "dinda", "yinda", "ige", "ge", "ina", "in", "n",
    # ── MARATHI / HINDI locative: -मध्ये -मधे -में
    "madhe", "madhye", "mein", "men",
    # ── MARATHI / HINDI genitive: -च्या -चा -ची -चे
    "chya", "cha", "chi", "che",
    # ── MARATHI / HINDI dative / locative endings
    "la", "na",
    # ── TELUGU locative: -లో -లోని -లోనే  (root must be >= 5 chars)
    "lo", "loni", "lone", "lona", "lonu", "loke", "lona",
    # ── TAMIL locative: -இல் → "il", -ல் → "l" (after inherent-vowel fix)
    "il", "yil", "vil",
    # ── MALAYALAM locative: -ൽ → "l" (chillu), -ത്തിൽ → "ttil", -ക്കിൽ → "kkil"
    "ttil", "kkil",
    # ── BENGALI / ASSAMESE locative: -তে → "te", -এ → "e" (bare, needs long root)
    "te", "ye",
    # ── GUJARATI locative: -માં → "man" / "maan"
    "maan", "man",
    # ── ODIA locative: -ରେ → "re"
    "re",
    # ── PUNJABI / GURMUKHI locative: -ਵਿੱਚ → "wich" / "vich"
    "wich", "vich",
    # ── URDU locative: میں → "myn" (after Arabic-script transliteration)
    "myn",
    # ── MALAYALAM / TAMIL locative with inherent-vowel forms after fix
    "ail", "eil", "oil",
)

_NATIVE_LOCATION_SUFFIXES = (
    # Kannada
    "ನಲ್ಲಿ", "ದಲ್ಲಿ", "ಯಲ್ಲಿ", "ಇಂದ", "ದಿಂದ", "ಯಿಂದ", "ಗೆ", "ಕ್ಕೆ", "ನ", "ದ",
    # Devanagari (Hindi/Marathi and related)
    "मध्ये", "मधे", "मध्येच", "मध्येही", "में", "पर", "ला", "ने", "च्या", "चा", "ची", "चे",
    # Telugu
    "లోని", "లోనే", "లో", "కి", "కు", "ని",
    # Tamil
    "யில்", "இல்", "க்கு", "இன்", "ல்", "ன்",
    # Malayalam
    "യിൽ", "ത്തില്", "യില്", "ല്", "ക്ക്", "ന്റെ",
    # Bengali / Assamese
    "তে", "তেই", "এর", "র", "এ",
    # Gujarati
    "માં", "મા", "ના", "ની", "ને",
    # Odia
    "ରେ", "ର", "କୁ",
    # Gurmukhi / Punjabi
    "ਵਿੱਚ", "ਚ", "ਦਾ", "ਦੀ", "ਦੇ",
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


def _build_assembly_bucket_key(
    seat_type: str | None,
    seat_name: str | None,
    assembly_name: str | None,
) -> str:
    clean_type = "mla" if normalize(seat_type or "") == "mla" else "mp"
    clean_seat = normalize(seat_name or "")
    clean_assembly = normalize(assembly_name or "")
    return f"{clean_type}:{clean_seat}/{clean_assembly}"

# --- HELPERS ---
def normalize(text: str) -> str:
    """Standardizes text: lower, no punctuation, single spaces."""
    if not text: return ""
    text = text.translate(str.maketrans('', '', string.punctuation))
    return re.sub(r"\s+", " ", text.lower().strip())


def _normalize_with_separators(text: str) -> str:
    """Standardize while preserving token boundaries around punctuation."""
    if not text:
        return ""
    translation = str.maketrans({char: " " for char in string.punctuation})
    text = text.translate(translation)
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
    # ── Pan-India phonetic normalizations ──────────────────────────────────
    # Each rule produces an EXTRA canonical form; the original is also kept.
    # Applied symmetrically to both query and index, so false matches cancel out.

    # v/w — 'व' maps to 'v' in transliteration but most Indian place-name
    # databases spell it 'w' (Wadi, Wada, Tilakwadi, Bhiwandi, Virar/Virar…).
    # Normalise to 'w' so both sides collide.
    value = value.replace("v", "w")

    # sh/s — common drift in Indian regional romanisation ("Shivaji"/"Sivaji",
    # "Sholapur"/"Solapur"). Applied at word boundaries only to limit false hits.
    value = re.sub(r"\bsh", "s", value)

    # zh/j — Tamil ழ (mazhai, kozhikode) is variously romanised as zh, z, j, l.
    value = value.replace("zh", "j")

    # Aspirated/plain collapse — in casual messages aspirated consonants are
    # often written as their plain equivalents or vice-versa.
    value = re.sub(r"\bkh", "k", value)
    value = re.sub(r"\bgh", "g", value)
    value = re.sub(r"\bph", "p", value)

    # Double-vowel normalisation (long → short for fuzzy matching)
    value = re.sub(r"(aa|ae)", "a", value)
    value = re.sub(r"(ee|ii)", "i", value)
    value = re.sub(r"(oo|uu)", "u", value)

    # Specific regional name normalisation
    value = value.replace("bastawad", "baswad")
    value = value.replace("bastwad", "baswad")
    value = value.replace("basawad", "baswad")
    value = value.replace("bsvad", "baswad")

    # Intervocalic /y/ drop ("Narayan" → "Narain", "Vijayan" → "Vijaan")
    value = re.sub(r"(?<=[aeiou])y(?=[aeiou])", "", value)
    value = re.sub(r"iya\b", "ia", value)

    value = re.sub(r"\s+", " ", value).strip()
    return value


def _build_location_token_variants(value: str) -> Set[str]:
    variants: Set[str] = set()
    for token in normalize(value).split():
        if len(token) < 4:
            continue
        candidates = {token}
        for suffix in _ROMAN_LOCATION_SUFFIXES:
            if token.endswith(suffix) and len(token) - len(suffix) >= 4:
                base = token[: -len(suffix)]
                if base:
                    candidates.add(base)
                    if suffix in {"alli", "nalli", "dalli", "yalli", "inalli", "inlli", "nlli"} and base.endswith("n"):
                        candidates.add(base[:-1])
                    if suffix in {"in", "ina", "n"} and not base.endswith(("a", "e", "i", "o", "u")):
                        candidates.add(f"{base}i")

        expanded = set(candidates)
        for candidate in candidates:
            canonical = _canonicalize_alias(candidate)
            if canonical:
                expanded.add(canonical)
            expanded.add(candidate.replace("gundri", "kundri"))
            expanded.add(candidate.replace("kundri", "gundri"))
            if candidate.endswith(("wad", "vad")):
                expanded.add(f"{candidate}i")
                expanded.add(f"{candidate[:-3]}wadi")
            if candidate.endswith(("wad", "vad", "wadi", "vadi")):
                expanded.add(candidate.replace("v", "w"))
                expanded.add(candidate.replace("w", "v"))
            if candidate.endswith("po"):
                expanded.add(f"{candidate}t")
            if candidate.endswith("depon"):
                expanded.add(candidate[:-1])
                expanded.add(f"{candidate[:-1]}t")
        variants.update(v for v in expanded if len(v) >= 4)
    return variants


def _speech_location_key(token: str) -> str:
    """
    Build a broad phonetic key for locality tokens, scoped later by tenant data.

    This deliberately avoids location-specific aliases. It handles common ASR
    drift in Indian locality names, especially village names ending in
    gaon/gav, where labials and retroflex/liquid sounds are often confused.
    """
    value = normalize(_transliterate(token))
    if not value:
        return ""
    value = _canonicalize_alias(value)
    for suffix in _ROMAN_LOCATION_SUFFIXES:
        if value.endswith(suffix) and len(value) - len(suffix) >= 5:
            value = value[: -len(suffix)]
            break
    value = re.sub(r"ga[vw]a$", "gav", value)
    value = value.replace("gaon", "gav")
    if not re.search(r"(gav|gao|gaw)$", value):
        return ""
    value = re.sub(r"(gav|gao|gaw)$", "g", value)
    value = re.sub(r"ph", "f", value)
    value = re.sub(r"[fvwmbp]", "b", value)
    value = re.sub(r"[tdrl]", "r", value)
    value = re.sub(r"[aeiou]", "", value)
    value = re.sub(r"(.)\1+", r"\1", value)
    return value if len(value) >= 3 else ""


def _speech_location_keys(forms: Iterable[str]) -> Set[str]:
    keys: Set[str] = set()
    for form in forms:
        for token in normalize(form).split():
            if len(token) < 5:
                continue
            key = _speech_location_key(token)
            if key:
                keys.add(key)
    return keys


def _build_match_forms(*texts: str) -> Set[str]:
    forms: Set[str] = set()
    for text in texts:
        if not text:
            continue
        normalized = normalize(text)
        if normalized:
            forms.add(normalized)
        separated = _normalize_with_separators(text)
        if separated:
            forms.add(separated)
            canonical = _canonicalize_alias(text)
            if canonical:
                forms.add(canonical)
        if _has_indic_script(text):
            native_variants = _build_native_location_variants(text)
            for native_variant in native_variants:
                native_normalized = normalize(native_variant)
                if native_normalized:
                    forms.add(native_normalized)
                transliterated = normalize(_transliterate(native_variant))
                if transliterated:
                    forms.add(transliterated)
                    canonical = _canonicalize_alias(transliterated)
                    if canonical:
                        forms.add(canonical)
                    forms.update(_build_location_token_variants(transliterated))
                    forms.update(_build_location_token_variants(canonical))
    return {form for form in forms if form}


def _build_native_location_variants(value: str) -> Set[str]:
    variants: Set[str] = {value}
    tokens = [token.strip() for token in re.split(r"\s+", str(value or "").strip()) if token.strip()]
    for token in tokens:
        if not _has_indic_script(token):
            continue
        token_variants = {token}
        for suffix in _NATIVE_LOCATION_SUFFIXES:
            current_variants = list(token_variants)
            for candidate in current_variants:
                if candidate.endswith(suffix) and len(candidate) - len(suffix) >= 2:
                    base = candidate[: -len(suffix)]
                    if base:
                        token_variants.add(base)
        variants.update(token_variants)
    return variants


def _confidence_level_for_match_type(match_type: str) -> str:
    value = str(match_type or "").lower()
    if value in {"exact_full", "exact_substring", "db_alias_exact", "god_mode"}:
        return "exact"
    if value in {"word_boundary", "spaceless", "db_alias_boundary"}:
        return "boundary"
    if value == "speech_phonetic":
        return "speech_phonetic"
    if value.startswith("fuzzy_") or value.startswith("fuzzy_phrase"):
        return "fuzzy"
    return "unknown"


def _station_seed_aliases(station: Dict[str, Any], parliamentary_constituency: Optional[str] = None) -> Set[str]:
    seeds: Set[str] = set()
    for field in ("locality", "locality_en", "mentioned_location_roman", "mentioned_location_original"):
        raw = str(station.get(field) or "").strip()
        if not raw:
            continue
        # Add full value (newlines -> space) as one seed.
        value = raw.replace("\n", " ").strip()
        if value:
            seeds.add(value)
        # Also index each line independently so multiline locality strings like
        # "Nath Pai Circle\nShahapur, Belagavi" can match on the prefix line alone.
        for line in raw.split("\n"):
            line = line.strip()
            if line and line != value:
                seeds.add(line)

    raw_aliases = station.get("aliases") or station.get("alias") or []
    if isinstance(raw_aliases, str):
        raw_aliases = re.split(r"[,;|]", raw_aliases)
    if isinstance(raw_aliases, (list, tuple, set)):
        for alias in raw_aliases:
            value = str(alias or "").replace("\n", " ").strip()
            if value:
                seeds.add(value)

    if station.get("sub_locality"):
        seeds.add(str(station.get("sub_locality")).strip())
    if station.get("parent_locality"):
        parent_locality = str(station.get("parent_locality")).strip()
        if parent_locality:
            seeds.add(parent_locality)
            if station.get("sub_locality"):
                sub_locality = str(station.get("sub_locality")).strip()
                if sub_locality:
                    seeds.add(f"{sub_locality} {parent_locality}")
                    seeds.add(f"{sub_locality}, {parent_locality}")

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
    dot_fragments = [fragment.strip() for fragment in raw.split(".") if fragment.strip()]
    if len(dot_fragments) > 1 and len(normalize(dot_fragments[0]).split()) >= 2:
        candidates.update(
            fragment for fragment in dot_fragments
            if len(normalize(fragment)) >= 4
        )

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


def _is_meaningful_location_fragment(value: str) -> bool:
    normalized = normalize(value)
    if not normalized or len(normalized) < 4:
        return False
    generic_only = {
        "road", "street", "lane", "galli", "gali", "wadi", "wada", "circle",
        "nagar", "peth", "pet", "area", "colony", "camp", "market", "road",
        "marg", "depot", "school", "college", "ward", "sector",
    }
    words = [word for word in normalized.split() if word]
    if not words:
        return False
    if all(word in generic_only for word in words):
        return False
    return True


def _preferred_parent_display(locality: str, parliamentary_constituency: Optional[str] = None) -> Optional[str]:
    aliases = {
        alias for alias in _derive_locality_aliases(locality, parliamentary_constituency)
        if _is_meaningful_location_fragment(alias)
    }
    if not aliases:
        normalized = normalize(locality)
        return _display_location_name(normalized) if _is_meaningful_location_fragment(normalized) else None
    ranked = sorted(
        aliases,
        key=lambda alias: (len(alias.split()), len(alias), alias),
    )
    return _display_location_name(ranked[0]) if ranked else None


def _preferred_specific_display(locality: str) -> Optional[str]:
    raw = (locality or "").replace("\n", " ").strip()
    if not raw:
        return None
    fragments = [fragment.strip() for fragment in re.split(r"[,.;/]", raw) if fragment.strip()]
    ranked = [
        fragment for fragment in fragments
        if _is_meaningful_location_fragment(fragment) and len(normalize(fragment).split()) >= 2
    ]
    if not ranked:
        return None
    ranked.sort(key=lambda fragment: (-len(normalize(fragment).split()), -len(normalize(fragment)), fragment))
    return _display_location_name(ranked[0])


def _build_parent_locality_catalog(
    stations: Iterable[Dict[str, Any]],
    parliamentary_constituency: Optional[str] = None,
) -> dict[str, str]:
    catalog: dict[str, str] = {}
    for station in stations or []:
        locality = (station.get("locality") or "").replace("\n", " ").strip()
        if not locality or _is_meta_locality(locality):
            continue
        preferred_display = _preferred_parent_display(locality, parliamentary_constituency)
        if not preferred_display:
            continue
        for alias in _derive_locality_aliases(preferred_display, parliamentary_constituency) | {preferred_display}:
            if not _is_meaningful_location_fragment(alias):
                continue
            catalog.setdefault(normalize(alias), preferred_display)
    return catalog


def _infer_station_hierarchy(
    station: Dict[str, Any],
    parent_catalog: dict[str, str],
    parliamentary_constituency: Optional[str] = None,
) -> Dict[str, Any]:
    locality = (station.get("locality") or "").replace("\n", " ").strip()
    if not locality or _is_meta_locality(locality):
        return station

    normalized_locality = normalize(locality)
    row_aliases = sorted(
        {
            alias for alias in _derive_locality_aliases(locality, parliamentary_constituency)
            if _is_meaningful_location_fragment(alias)
        },
        key=lambda alias: (-len(alias), alias),
    )
    sorted_candidates = sorted(
        parent_catalog.items(),
        key=lambda item: (-len(item[0]), item[0]),
    )
    parent_locality: Optional[str] = None
    sub_locality: Optional[str] = None

    for candidate_alias, candidate_display in sorted_candidates:
        if not candidate_alias:
            continue
        for row_alias in row_aliases:
            if row_alias == candidate_alias:
                continue
            if not row_alias.endswith(f" {candidate_alias}"):
                continue
            prefix = row_alias[: -len(candidate_alias)].strip(" ,-/")
            if not _is_meaningful_location_fragment(prefix):
                continue
            parent_locality = candidate_display
            sub_locality = _display_location_name(prefix)
            break
        if parent_locality and sub_locality:
            break

    enriched = dict(station)
    if parent_locality and sub_locality:
        enriched["parent_locality"] = parent_locality
        enriched["sub_locality"] = sub_locality
        enriched["hierarchy_type"] = "sub_locality"
        raw_aliases = enriched.get("aliases") or []
        if isinstance(raw_aliases, str):
            raw_aliases = re.split(r"[,;|]", raw_aliases)
        aliases = {str(alias or "").strip() for alias in raw_aliases if str(alias or "").strip()}
        aliases.update(
            {
                sub_locality,
                parent_locality,
                f"{sub_locality} {parent_locality}",
                f"{sub_locality}, {parent_locality}",
            }
        )
        enriched["aliases"] = sorted(aliases)
    else:
        enriched["hierarchy_type"] = enriched.get("hierarchy_type") or "locality"
    return enriched


def _annotate_station_hierarchy(
    stations: Iterable[Dict[str, Any]],
    parliamentary_constituency: Optional[str] = None,
) -> list[Dict[str, Any]]:
    station_list = [dict(station) for station in (stations or [])]
    parent_catalog = _build_parent_locality_catalog(station_list, parliamentary_constituency)
    return [
        _infer_station_hierarchy(station, parent_catalog, parliamentary_constituency)
        for station in station_list
    ]


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


def _collect_generated_alias_collisions(
    *,
    seat_type: str | None,
    seat_name: str | None,
    parliamentary_constituency: str,
    assembly: str,
    stations: Iterable[Dict[str, Any]],
    other_rows: Iterable[Dict[str, Any]],
) -> Dict[str, list]:
    current_aliases: Dict[str, Set[str]] = {}
    current_base_forms: Dict[str, Set[str]] = {}

    for station in stations:
        locality = (station.get("locality") or "").replace("\n", " ").strip()
        if not locality or _is_meta_locality(locality):
            continue
        base_seed_values: Set[str] = set()
        for field in ("locality", "locality_en", "mentioned_location_roman", "mentioned_location_original"):
            raw = str(station.get(field) or "").strip()
            if not raw:
                continue
            value = raw.replace("\n", " ").strip()
            if value:
                base_seed_values.add(value)
            for line in raw.split("\n"):
                line = line.strip()
                if line and line != value:
                    base_seed_values.add(line)
        raw_aliases = station.get("aliases") or station.get("alias") or []
        if isinstance(raw_aliases, str):
            raw_aliases = re.split(r"[,;|]", raw_aliases)
        if isinstance(raw_aliases, (list, tuple, set)):
            for alias in raw_aliases:
                value = str(alias or "").replace("\n", " ").strip()
                if value:
                    base_seed_values.add(value)
        base_forms: Set[str] = set()
        for seed in base_seed_values:
            base_forms.update(_build_match_forms(seed))
        generated_forms = _generated_alias_forms(station, parliamentary_constituency)
        derived_aliases = {
            form for form in generated_forms
            if form and form not in base_forms and len(form) >= 5
        }
        if derived_aliases:
            current_aliases[locality] = derived_aliases
            current_base_forms[locality] = base_forms

    collisions: Dict[str, Set[str]] = {}
    clean_seat_type = normalize(seat_type or "")
    clean_seat_name = normalize(seat_name or parliamentary_constituency)
    for row in other_rows:
        row_seat_type = normalize(row.get("seat_type") or "mp")
        row_seat_name = normalize(row.get("seat_name") or row.get("parliamentary_constituency") or "")
        if row_seat_type != clean_seat_type or row_seat_name != clean_seat_name:
            continue
        if row.get("assembly") == assembly:
            continue
        for station in row.get("stations") or []:
            other_locality = (station.get("locality") or "").replace("\n", " ").strip()
            if not other_locality or _is_meta_locality(other_locality):
                continue
            other_forms = _generated_alias_forms(station, parliamentary_constituency)
            for locality, aliases in current_aliases.items():
                overlapping = aliases & other_forms
                if overlapping:
                    for alias in overlapping:
                        if alias in current_base_forms.get(locality, set()):
                            continue
                        collisions.setdefault(alias, set()).add(row.get("assembly", ""))

    return {
        alias: sorted(assemblies)
        for alias, assemblies in sorted(collisions.items())
        if assemblies
    }


def sanitize_and_validate_stations(
    stations: Iterable[Dict[str, Any]],
    *,
    parliamentary_constituency: Optional[str] = None,
    assembly: Optional[str] = None,
    seat_type: Optional[str] = None,
    seat_name: Optional[str] = None,
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

    cleaned = _annotate_station_hierarchy(cleaned, parliamentary_constituency)

    ambiguity_report: Dict[str, list] = {}
    alias_collision_report: Dict[str, list] = {}
    if parliamentary_constituency and assembly and other_rows is not None:
        ambiguity_report = _collect_constituency_ambiguities(
            parliamentary_constituency,
            assembly,
            cleaned,
            other_rows,
        )
        alias_collision_report = _collect_generated_alias_collisions(
            seat_type=seat_type,
            seat_name=seat_name,
            parliamentary_constituency=parliamentary_constituency,
            assembly=assembly,
            stations=cleaned,
            other_rows=other_rows,
        )

    alias_form_counts = []
    low_coverage_samples: list[str] = []
    for station in cleaned:
        alias_count = len(_generated_alias_forms(station, parliamentary_constituency))
        alias_form_counts.append(alias_count)
        if alias_count <= 1 and len(low_coverage_samples) < 20:
            low_coverage_samples.append(station["locality"])

    weak_coverage_reasons: list[str] = []
    if cleaned:
        missing_locality_en_ratio = sum(1 for station in cleaned if not station.get("locality_en")) / len(cleaned)
        limited_alias_ratio = sum(1 for count in alias_form_counts if count <= 1) / len(cleaned)
        if missing_locality_en_ratio >= 0.5:
            weak_coverage_reasons.append("more_than_half_rows_missing_locality_en")
        if limited_alias_ratio >= 0.35:
            weak_coverage_reasons.append("many_rows_have_only_one_alias_form")

    report = {
        "rows_received": len(list(stations or [])) if not isinstance(stations, list) else len(stations),
        "rows_saved": len(cleaned),
        "meta_rows_removed": len(removed_meta_rows),
        "meta_row_samples": removed_meta_rows[:20],
        "duplicate_localities_in_upload": duplicate_localities_in_upload,
        "ambiguous_localities_against_constituency": ambiguity_report,
        "alias_collisions_against_seat": alias_collision_report,
        "missing_locality_en_count": sum(1 for station in cleaned if not station.get("locality_en")),
        "missing_locality_en_samples": missing_locality_en_samples[:20],
        "distinct_generated_alias_forms": len({form for station in cleaned for form in _generated_alias_forms(station, parliamentary_constituency)}),
        "average_generated_alias_forms_per_row": round(sum(alias_form_counts) / len(alias_form_counts), 2) if alias_form_counts else 0,
        "rows_with_single_generated_alias_form": sum(1 for count in alias_form_counts if count <= 1),
        "weak_coverage_warning": bool(weak_coverage_reasons),
        "weak_coverage_reasons": weak_coverage_reasons,
        "weak_coverage_samples": low_coverage_samples,
        "blocking_errors": ["alias_collisions_against_seat"] if alias_collision_report else [],
    }
    return cleaned, report

def get_keywords(text: str, *, allow_generic_locations: bool = False) -> set:
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
        "gate", "bridge", "hospital", "temple",
        "masjid", "church", "railway", "bus", "stop", "circle", "square",
        # Indian location generic
        "bazar", "bazaar", "peth", "pet", "galli", "gali", "wadi", "wada",
        "gaon", "goan", "pada", "pura", "pur", "abad", "ghat", "khurd",
        "budruk", "tarf", "road", "marg", "path", "math", "devi",
        "maharaj", "govt", "government", "english",
        "medium", "kannada", "marathi", "urdu", "hindi",
        "building", "room", "hall", "office",
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
    if allow_generic_locations:
        stopwords -= {
            "school", "college", "depot", "vaccine", "circle", "market",
            "primary", "high", "gate", "bridge", "bus", "stop",
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
                        row.get("seat_type") or "mp",
                        row.get("seat_name") or row["parliamentary_constituency"],
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
                sources.append(("mp", parl_name, parl_name, json_file.stem, stations))

    for seat_type, seat_name, parl_name, assembly, stations in sources:
        annotated_stations = _annotate_station_hierarchy(stations, parl_name)
        bucket_key = _build_assembly_bucket_key(seat_type, seat_name, assembly)
        if bucket_key not in _geography_index["assemblies"]:
            _geography_index["assemblies"][bucket_key] = {
                "seat_type": "mla" if normalize(seat_type) == "mla" else "mp",
                "seat_name": seat_name,
                "parl": parl_name,
                "assembly": assembly,
                "entries": [],
            }

        for s in annotated_stations:
            raw_loc = s.get("locality", "").replace("\n", " ").strip()
            raw_bldg = s.get("building_name", "").replace("\n", " ").strip()
            station = str(s.get("station_number", "")).strip()
            hierarchy_type = str(s.get("hierarchy_type") or "locality").strip()
            parent_locality = (s.get("parent_locality") or "").replace("\n", " ").strip() or None
            sub_locality = (s.get("sub_locality") or "").replace("\n", " ").strip() or None

            norm_loc = normalize(raw_loc)
            raw_loc_en = s.get("locality_en", "").replace("\n", " ").strip()
            if not norm_loc or _is_meta_locality(raw_loc):
                continue

            match_forms = _generated_alias_forms(s, parl_name)
            specific_station = dict(s)
            if parent_locality:
                specific_station["parent_locality"] = None
            specific_match_forms = _generated_alias_forms(specific_station, parl_name)
            parent_match_forms: Set[str] = set()
            if parent_locality:
                parent_station = {
                    "locality": parent_locality,
                    "locality_en": parent_locality,
                    "building_name": parent_locality,
                }
                parent_match_forms = _generated_alias_forms(parent_station, parl_name)
            spaceless_match_forms = _spaceless_forms(match_forms)
            speech_match_forms = _speech_location_keys(match_forms)
            keywords = set()
            for form in match_forms:
                keywords |= get_keywords(form)
            specific_keywords = set()
            for form in specific_match_forms:
                specific_keywords |= get_keywords(form, allow_generic_locations=True)
            keywords |= get_keywords(raw_bldg)
            speech_match_forms.update(_speech_location_keys(keywords))
            speech_match_forms.update(_speech_location_keys(specific_keywords))

            _geography_index["assemblies"][bucket_key]["entries"].append({
                "orig_name": raw_loc,
                "match_forms": match_forms,
                "specific_match_forms": specific_match_forms,
                "parent_match_forms": parent_match_forms,
                "spaceless_match_forms": spaceless_match_forms,
                "speech_match_forms": speech_match_forms,
                "station": station,
                "keywords": keywords,
                "specific_keywords": specific_keywords,
                "hierarchy_type": hierarchy_type,
                "parent_locality": parent_locality,
                "sub_locality": sub_locality,
            })
            _register_entry_ambiguities(parl_name, assembly, match_forms)
            _register_entry_ambiguities(parl_name, assembly, spaceless_match_forms)
        files_loaded += 1
        logger.debug(f"   Indexed {assembly}: {len(stations)} locations")

    _geography_index["loaded"] = True
    return files_loaded > 0


def _get_tenant_seat_context(tenant_id: int | None) -> Optional[Dict[str, str]]:
    if not tenant_id:
        return None

    tenant = None
    raw_constituency = None
    try:
        from sansadx_backend.db import SessionLocal, Tenant, derive_seat_type
        db = SessionLocal()
        try:
            tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first()
            if tenant and tenant.constituency:
                raw_constituency = tenant.constituency
                seat_type = derive_seat_type(tenant)
                scope = raw_constituency
                if seat_type == "mla":
                    scope = get_assembly_parliamentary_constituency(raw_constituency) or raw_constituency
                return {
                    "seat_type": seat_type,
                    "seat_name": raw_constituency,
                    "scope_parliamentary": scope,
                    "constituency": raw_constituency,
                }
        finally:
            db.close()
    except Exception:
        pass

    if not raw_constituency:
        try:
            override_paths = [
                PROJECT_ROOT / "tenant_overrides.json",
                Path("tenant_overrides.json").resolve(),
            ]
            for op in override_paths:
                if not op.exists():
                    continue
                with open(op, "r", encoding="utf-8") as f:
                    data = json.load(f)
                tenant_data = data.get("tenants", {}).get(str(tenant_id), {})
                raw_constituency = tenant_data.get("constituency")
                if raw_constituency:
                    seat_type = "mla" if normalize(tenant_data.get("seat_type", "")) == "mla" else "mp"
                    scope = raw_constituency
                    if seat_type == "mla":
                        scope = get_assembly_parliamentary_constituency(raw_constituency) or raw_constituency
                    return {
                        "seat_type": seat_type,
                        "seat_name": raw_constituency,
                        "scope_parliamentary": scope,
                        "constituency": raw_constituency,
                    }
        except Exception:
            pass

    return None

# --- RESOLVER ---
def _rank_location_candidates(
    text: str,
    *,
    scope_parliamentary: Optional[str] = None,
    tenant_id: Optional[int] = None,
) -> list[Dict[str, Any]]:
    if not text:
        return []
    if not _geography_index["loaded"]:
        load_geography_index()

    query_forms = _build_match_forms(text)
    if not query_forms:
        return []

    clean_text = max(query_forms, key=len)
    spaceless_query_forms = _spaceless_forms(query_forms)
    spaceless_query_phrase_forms = _spaceless_phrase_forms(query_forms)
    speech_query_forms = _speech_location_keys(query_forms)
    user_keywords = set()
    for form in query_forms:
        user_keywords |= get_keywords(form)
    specific_user_keywords = set()
    for form in query_forms:
        specific_user_keywords |= get_keywords(form, allow_generic_locations=True)
    
    logger.debug(f"RESOLVING: '{clean_text}' (tenant={tenant_id})")
    tenant_context = _get_tenant_seat_context(tenant_id) if tenant_id is not None else None

    # 1. TENANT-SPECIFIC OVERRIDES (from tenant_overrides.json)
    if tenant_id is not None:
        tenant_aliases = _load_tenant_geo_aliases(int(tenant_id))
        for alias_key, payload in tenant_aliases.items():
            alias_forms = _build_match_forms(alias_key)
            if not alias_forms:
                continue
            if alias_forms & query_forms:
                return [{
                    "location_resolved": True,
                    "assembly_constituency": payload["assembly"],
                    "matched_value": _display_location_name(payload["display"]),
                    "confidence": "db_alias_exact",
                    "confidence_level": "exact",
                    "match_type": "db_alias_exact",
                    "assembly": payload["assembly"],
                    "parl": scope_parliamentary or (tenant_context or {}).get("scope_parliamentary"),
                    "seat_type": (tenant_context or {}).get("seat_type"),
                    "seat_name": (tenant_context or {}).get("seat_name"),
                    "name": payload["display"],
                    "matched_name": _display_location_name(payload["display"]),
                    "score": 1000,
                    "type": "db_alias_exact",
                }]
            for alias_form in alias_forms:
                if len(alias_form) >= 5 and any(re.search(r'\b' + re.escape(alias_form) + r'\b', qf) for qf in query_forms):
                    return [{
                        "location_resolved": True,
                        "assembly_constituency": payload["assembly"],
                        "matched_value": _display_location_name(payload["display"]),
                        "confidence": "db_alias_boundary",
                        "confidence_level": "boundary",
                        "match_type": "db_alias_boundary",
                        "assembly": payload["assembly"],
                        "parl": scope_parliamentary or (tenant_context or {}).get("scope_parliamentary"),
                        "seat_type": (tenant_context or {}).get("seat_type"),
                        "seat_name": (tenant_context or {}).get("seat_name"),
                        "name": payload["display"],
                        "matched_name": _display_location_name(payload["display"]),
                        "score": 980,
                        "type": "db_alias_boundary",
                    }]

        tenant_overrides = _load_tenant_overrides(tenant_id)
        for k, v in tenant_overrides.items():
            if k.lower() in clean_text:
                logger.debug(f"   OVERRIDE (tenant {tenant_id}): {k} -> {v}")
                return [{
                    "location_resolved": True,
                    "assembly_constituency": v,
                    "matched_value": k.title(),
                    "confidence": "god_mode",
                    "confidence_level": "exact",
                    "match_type": "god_mode",
                    "assembly": v,
                    "parl": scope_parliamentary or (tenant_context or {}).get("scope_parliamentary"),
                    "seat_type": (tenant_context or {}).get("seat_type"),
                    "seat_name": (tenant_context or {}).get("seat_name"),
                    "name": k.title(),
                    "matched_name": k.title(),
                    "score": 990,
                    "type": "god_mode",
                }]

    seat_scope_type = normalize((tenant_context or {}).get("seat_type", ""))
    seat_scope_name = normalize((tenant_context or {}).get("seat_name", ""))

    candidates = []

    for _, data in _geography_index["assemblies"].items():
        if tenant_context:
            if seat_scope_type and normalize(data.get("seat_type", "")) != seat_scope_type:
                continue
            if seat_scope_name and normalize(data.get("seat_name", "")) != seat_scope_name:
                continue
        elif scope_parliamentary and normalize(data["parl"]) != normalize(scope_parliamentary):
            continue

        for entry in data["entries"]:
            score = 0
            match_type = "none"
            matched_name = entry["orig_name"]
            matched_type = str(entry.get("hierarchy_type") or "locality")
            matched_value = entry.get("sub_locality") or entry["orig_name"]
            entry_forms = entry.get("match_forms", set())
            entry_specific_forms = entry.get("specific_match_forms", set()) or entry_forms
            entry_parent_forms = entry.get("parent_match_forms", set())
            entry_spaceless_forms = entry.get("spaceless_match_forms", set())
            entry_speech_forms = entry.get("speech_match_forms", set())
            entry_specific_keywords = entry.get("specific_keywords", set())
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

            # F2. SPEECH PHONETIC MATCH — tenant-scoped and accepted only
            # through normal candidate ambiguity checks. Handles ASR drift like
            # "फळगावच्या" when the known locality is a *gaon/*gav village.
            if score == 0 and entry_speech_forms and speech_query_forms:
                speech_matches = entry_speech_forms & speech_query_forms
                if speech_matches:
                    matched_form = max(speech_matches, key=len)
                    score = 86 + len(matched_form)
                    match_type = "speech_phonetic"
                    matching_names = [
                        form for form in entry_forms
                        if _speech_location_key(form) == matched_form
                    ]
                    matched_name = min(matching_names, key=len) if matching_names else entry["orig_name"]

            # G. FUZZY KEYWORD MATCH — STRICT (93% similarity, min 6 char keywords)
            # Catches common Indian spelling variants like "Budhwar"/"Budhawar"
            # and "Tilkwadi"/"Tilakwadi" without opening the gate too wide.
            if score == 0:
                for uk in user_keywords:
                    if len(uk) < 6: continue
                    for dk in entry["keywords"]:
                        if len(dk) < 6: continue
                        # Only consider if lengths are similar (±25%)
                        if not (0.75 <= len(uk)/len(dk) <= 1.25):
                            continue
                        sim = similarity_score(uk, dk)
                        if sim > 90:  # lowered from 93: pan-India scripts produce
                            # slightly imperfect romanizations; 90% still rejects
                            # genuinely-different-romanization cases (Delhi, Mumbai)
                            # which score 67-74% and need the alias DB instead.
                            score = sim
                            match_type = f"fuzzy_strict ({uk}~{dk})"
                            matched_name = dk
                            break
                    if score > 0:
                        break

            if score == 0 and entry_specific_keywords:
                for uk in specific_user_keywords:
                    if len(uk) < 4:
                        continue
                    for dk in entry_specific_keywords:
                        if len(dk) < 4:
                            continue
                        if not (0.7 <= len(uk) / len(dk) <= 1.35):
                            continue
                        sim = similarity_score(uk, dk)
                        if sim > 84:
                            score = 88 + (sim / 20)
                            match_type = f"fuzzy_specific ({uk}~{dk})"
                            matched_name = dk
                            break
                    if score > 0:
                        break

            normalized_matched_name = normalize(matched_name)
            if entry_parent_forms and normalized_matched_name in entry_parent_forms:
                matched_type = "locality"
                matched_value = entry.get("parent_locality") or _preferred_parent_display(entry["orig_name"], data.get("parl")) or entry["orig_name"] or matched_name
            else:
                matched_type = "sub_locality" if entry.get("sub_locality") else "locality"
                preferred_specific_display = _preferred_specific_display(entry["orig_name"])
                preferred_sub_locality = entry.get("sub_locality")
                if (
                    preferred_specific_display
                    and preferred_sub_locality
                    and len(normalize(str(preferred_sub_locality)).split()) == 1
                ):
                    preferred_sub_locality = preferred_specific_display
                matched_value = (
                    preferred_sub_locality
                    or entry.get("parent_locality")
                    or _preferred_parent_display(entry["orig_name"], data.get("parl"))
                    or entry["orig_name"]
                    or matched_name
                )

            # Only accept matches with score > 70 (raised threshold)
            if score > 70:
                candidates.append({
                    "assembly": data["assembly"],
                    "parl": data["parl"],
                    "seat_type": data.get("seat_type"),
                    "seat_name": data.get("seat_name"),
                    "name": entry["orig_name"],
                    "matched_name": _display_location_name(matched_name),
                    "matched_value": _display_location_name(str(matched_value)),
                    "matched_type": matched_type,
                    "parent_locality": entry.get("parent_locality"),
                    "score": score,
                    "type": match_type
                })

    candidates.sort(
        key=lambda x: (
            -x["score"],
            0 if x.get("matched_type") == "sub_locality" else 1,
            len(x.get("matched_name") or ""),
            len(x["name"]),
        )
    )
    return candidates


def suggest_location_candidates(
    text: str,
    *,
    scope_parliamentary: Optional[str] = None,
    tenant_id: Optional[int] = None,
    limit: int = 5,
) -> list[Dict[str, Any]]:
    candidates = _rank_location_candidates(
        text,
        scope_parliamentary=scope_parliamentary,
        tenant_id=tenant_id,
    )
    if not candidates:
        return []
    suggestions: list[Dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for candidate in candidates:
        key = (str(candidate.get("assembly") or ""), str(candidate.get("matched_name") or ""))
        if key in seen:
            continue
        seen.add(key)
        suggestions.append({
            "matched_value": candidate["matched_value"],
            "matched_type": candidate.get("matched_type"),
            "parent_locality": candidate.get("parent_locality"),
            "assembly_constituency": candidate["assembly"],
            "parliamentary_constituency": candidate.get("parl"),
            "seat_type": candidate.get("seat_type"),
            "seat_name": candidate.get("seat_name"),
            "score": candidate["score"],
            "match_type": candidate["type"],
            "confidence_level": _confidence_level_for_match_type(candidate["type"]),
        })
        if len(suggestions) >= max(1, int(limit)):
            break
    return suggestions


def resolve_location(text: str, scope_parliamentary: Optional[str] = None, tenant_id: Optional[int] = None) -> Dict[str, Any]:
    if not text:
        return {"location_resolved": False}
    candidates = _rank_location_candidates(
        text,
        scope_parliamentary=scope_parliamentary,
        tenant_id=tenant_id,
    )
    if not candidates:
        return {"location_resolved": False}

    winner = candidates[0]
    top_score = winner["score"]
    top_candidates = [c for c in candidates if c["score"] == top_score]
    top_assemblies = sorted({candidate["assembly"] for candidate in top_candidates})
    if len(top_assemblies) > 1:
        return {
            "location_resolved": False,
            "reason": "ambiguous_match",
            "ambiguous_assemblies": top_assemblies,
            "matched_value": winner["matched_value"],
            "matched_type": winner.get("matched_type"),
            "parent_locality": winner.get("parent_locality"),
            "parliamentary_constituency": winner["parl"],
            "confidence_level": "unknown",
        }

    logger.debug(f"   WINNER: {winner['name']} ({winner['assembly']}) - Score: {winner['score']:.1f} [{winner['type']}]")
    
    return {
        "location_resolved": True,
        "assembly_constituency": winner["assembly"],
        "parliamentary_constituency": winner["parl"],
        "matched_value": winner["matched_value"],
        "matched_type": winner.get("matched_type"),
        "parent_locality": winner.get("parent_locality"),
        "confidence": "high",
        "confidence_level": _confidence_level_for_match_type(winner["type"]),
        "match_type": winner["type"],
    }

# --- WRAPPERS ---
def _get_tenant_constituency(tenant_id):
    """Return the parliamentary constituency for a given tenant_id.

    MP tenants already store the parliamentary constituency directly.
    MLA tenants store the assembly name; for those we resolve assembly -> parent
    parliamentary constituency so scope filtering can still work.
    """
    if not tenant_id:
        return None
    tenant_context = _get_tenant_seat_context(tenant_id)
    if not tenant_context:
        return None
    return tenant_context.get("scope_parliamentary")

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


def assembly_belongs_to_parliamentary(
    assembly: str | None,
    parliamentary_constituency: str | None,
) -> bool:
    """Return True only when an assembly is indexed under the given parliamentary constituency."""
    if not assembly or not parliamentary_constituency:
        return False
    if not _geography_index["loaded"]:
        load_geography_index()

    assembly_norm = normalize(assembly)
    parliament_norm = normalize(parliamentary_constituency)
    for data in _geography_index["assemblies"].values():
        if normalize(data.get("assembly", "")) == assembly_norm and normalize(data.get("parl", "")) == parliament_norm:
            return True
    return False


def get_assembly_parliamentary_constituency(assembly: str | None) -> str | None:
    """Return the indexed parliamentary constituency for an assembly, if known."""
    if not assembly:
        return None
    if not _geography_index["loaded"]:
        load_geography_index()

    assembly_norm = normalize(assembly)
    matches = {
        str(data.get("parl") or "").strip()
        for data in _geography_index["assemblies"].values()
        if normalize(data.get("assembly", "")) == assembly_norm and str(data.get("parl") or "").strip()
    }
    if len(matches) == 1:
        return next(iter(matches))
    return None


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
    seat_to_tenants = {}
    try:
        from sansadx_backend.db import SessionLocal, Tenant, get_all_geography_data, build_seat_key, derive_seat_type
        db = SessionLocal()
        tenant_rows = db.query(Tenant).all()
        for t in tenant_rows:
            if not t.constituency or t.constituency == "System":
                continue
            seat_to_tenants.setdefault(build_seat_key(derive_seat_type(t), t.constituency), []).append(t.id)
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
                    "tenant_id": None,
                    "seat_type": "mp",
                    "seat_name": parl_dir.name,
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
        seat_type = row.get("seat_type") or "mp"
        seat_name = row.get("seat_name") or parl_name
        tenant_ids = seat_to_tenants.get(build_seat_key(seat_type, seat_name), [])
        if not tenant_ids:
            logger.info(f"No tenant found for seat '{seat_type}:{seat_name}', skipping override generation")
            continue
        for tenant_id in tenant_ids:
            grouped_rows.setdefault((seat_type, seat_name, parl_name, tenant_id), []).append(row)

    for (_seat_type, seat_name, parl_name, tenant_id), rows in grouped_rows.items():
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
