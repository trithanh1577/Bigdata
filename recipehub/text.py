from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from functools import cache
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
CULINARY_TERM_ALIASES = {
    "nhat ban": "japanese", "japan": "japanese", "viet nam": "vietnamese", "vietnam": "vietnamese",
    "han quoc": "korean", "south korea": "korean", "thai lan": "thai", "italy": "italian",
    "ca chua": "tomato", "ga": "chicken", "thit ga": "chicken", "thit bo": "beef", "bo": "beef",
    "thit heo": "pork", "thit lon": "pork", "heo": "pork", "lon": "pork", "tom": "shrimp",
    "tep": "shrimp", "ca hoi": "salmon", "ca": "fish", "com": "rice", "gao": "rice",
    "trung": "egg", "dau phong": "peanut", "hanh tay": "onion", "hanh": "onion", "toi": "garlic",
    "khoai tay": "potato", "nam": "mushroom", "rau": "vegetable", "pho mai": "cheese",
    "nuoc mam": "fish sauce", "nuoc tuong": "soy sauce", "bot mi": "flour", "mi": "noodles",
    "bun": "rice noodles", "ca ri": "curry", "dua": "coconut", "duong": "sugar", "muoi": "salt",
    "main course": "main course", "mon chinh": "main course", "mon khai vi": "appetizer",
    "mon trang mieng": "dessert", "mon canh": "soup",
    "mi y": "pasta", "sua": "milk", "sua tuoi": "milk", "dau nanh": "soy",
    "lac": "peanut", "dau phung": "peanut", "vung": "sesame", "me": "sesame",
    "lua mi": "wheat", "hat dieu": "cashew", "hanh nhan": "almond", "sot": "sauce",
    "hai san": "seafood", "trung ga": "egg", "ot": "chili", "chanh": "lime",
}

# Keep source wording as an alternative to the translated search term. Replacing
# words outright would stop titles such as "Bo kho" from matching their source.
_CULINARY_GROUPS: dict[str, list[str]] = {}
for _alias, _canonical in CULINARY_TERM_ALIASES.items():
    _CULINARY_GROUPS.setdefault(_canonical, [_canonical]).append(_alias)
for _canonical, _aliases in {
    "peanut": ["peanuts", "groundnut", "groundnuts", "đậu phộng", "đậu phụng"],
    "soy": ["soya", "soybean", "soybeans", "đậu nành"],
    "shrimp": ["prawn", "prawns", "shrimps"],
    "egg": ["eggs"], "milk": ["sữa", "sữa tươi"],
    "wheat": ["lúa mì"], "cashew": ["cashews", "hạt điều"],
    "almond": ["almonds"], "sesame": ["vừng", "mè"],
    "tofu": ["đậu phụ", "đậu hũ", "dau phu", "dau hu"],
    "ginger": ["gừng", "gung"], "carrot": ["cà rốt", "ca rot"],
}.items():
    _CULINARY_GROUPS.setdefault(_canonical, [_canonical]).extend(_aliases)


def _culinary_fold(value: str) -> str:
    return normalize_text(value).replace("đ", "d")


@cache
def _culinary_vocabulary() -> dict[str, tuple[str, list[str]]]:
    vocabulary = {}
    for canonical, variants in _CULINARY_GROUPS.items():
        for variant in variants:
            vocabulary[_culinary_fold(variant)] = (canonical, variants)
    return vocabulary


def culinary_query_groups(value: str) -> list[list[str]]:
    """Return bilingual phrase alternatives without losing the original query."""
    vocabulary = _culinary_vocabulary()
    words = re.findall(r"[^\W_]+", normalize_text(value), flags=re.UNICODE)
    groups = []
    index = 0
    longest = max(len(term.split()) for term in vocabulary)
    while index < len(words):
        for count in range(min(longest, len(words) - index), 0, -1):
            phrase = " ".join(words[index:index + count])
            entry = vocabulary.get(_culinary_fold(phrase))
            if entry:
                groups.append(list(dict.fromkeys([phrase, *entry[1]])))
                index += count
                break
        else:
            groups.append([words[index]])
            index += 1
    return groups


def ingredient_exclusion_terms(value: str) -> list[str]:
    """Expand a supplied ingredient name to known English/Vietnamese aliases."""
    entry = _culinary_vocabulary().get(_culinary_fold(value))
    return list(dict.fromkeys([value, *(entry[1] if entry else [])]))


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = html.unescape(value)
    if "<" in decoded and ">" in decoded:
        decoded = BeautifulSoup(decoded, "html.parser").get_text(" ")
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", decoded)).strip()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean_text(value).lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def normalize_recipe_query(value: str) -> str:
    """Map common Vietnamese recipe terms and country names to source vocabulary."""
    vocabulary = _culinary_vocabulary()
    pattern = r"(?<!\w)(?:" + "|".join(re.escape(term) for term in sorted(vocabulary, key=len, reverse=True)) + r")(?!\w)"
    return re.sub(pattern, lambda match: vocabulary[match[0]][0], _culinary_fold(value))


def tokens(value: str) -> list[str]:
    return TOKEN_RE.findall(normalize_text(value))


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    ignored = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid"}
    query = [(key, val) for key, val in parse_qsl(parts.query) if key.lower() not in ignored]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

