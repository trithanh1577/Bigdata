from __future__ import annotations

import hashlib
import html
import re
import unicodedata
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
}


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = BeautifulSoup(html.unescape(value), "html.parser").get_text(" ")
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", decoded)).strip()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean_text(value).lower())
    return "".join(char for char in value if not unicodedata.combining(char))


def normalize_recipe_query(value: str) -> str:
    """Map common Vietnamese recipe terms and country names to source vocabulary."""
    result = normalize_text(value)
    for term, canonical in sorted(CULINARY_TERM_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        result = re.sub(rf"\b{re.escape(term)}\b", canonical, result)
    return result


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

