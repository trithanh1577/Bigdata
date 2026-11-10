from __future__ import annotations

import hashlib
import html
import os
import re
import threading
import unicodedata
from pathlib import Path

from bs4 import BeautifulSoup


WHITESPACE_RE = re.compile(r"\s+")


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    decoded = html.unescape(value)
    if "<" in decoded and ">" in decoded:
        decoded = BeautifulSoup(decoded, "html.parser").get_text(" ")
    return WHITESPACE_RE.sub(" ", unicodedata.normalize("NFC", decoded)).strip()


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", clean_text(value).lower().replace("đ", "d"))
    return "".join(char for char in value if not unicodedata.combining(char))


def stable_id(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_text_atomic(path: Path, text: str) -> None:
    """Write via a temp file unique to this process and thread, then swap it in.

    The chat's web discovery and the `schedule` command can normalize at the same
    time; a shared "file.tmp" name let one writer overwrite or delete the other's file.
    """
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
