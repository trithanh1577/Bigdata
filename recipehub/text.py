from __future__ import annotations

import hashlib
import html
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")
TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = BeautifulSoup(html.unescape(value), "html.parser").get_text(" ")
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", decoded)).strip()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean_text(value).lower())
    return "".join(char for char in value if not unicodedata.combining(char))


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

