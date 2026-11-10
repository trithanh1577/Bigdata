from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from recipehub.models import validate_recipe


INDEX_VERSION = 1  # bump when fold() or indexed text changes, to re-index existing databases
# Common Vietnamese food words (accent-folded) -> English words used by the source records.
# Only single-meaning words: "bo" (bò/bơ), "toi" (tôi/tỏi), "nam" (nấm/Nam) are left out on purpose.
VI_FOOD_TERMS = {
    "ca chua": "tomato", "thit bo": "beef", "thit ga": "chicken", "thit heo": "pork", "thit lon": "pork",
    "hai san": "seafood", "trung ga": "egg", "trung": "egg", "tom": "shrimp", "cua": "crab", "gao": "rice",
    "com": "rice", "hanh": "onion", "gung": "ginger", "khoai tay": "potato", "ca rot": "carrot",
    "dau phu": "tofu", "sua": "milk", "pho mai": "cheese", "chanh": "lime", "ot": "chili", "ga": "chicken",
    "dau phong": "peanut", "lac": "peanut", "dau nanh": "soy", "bot mi": "flour", "lua mi": "wheat",
    "me": "sesame", "hat dieu": "cashew", "ca": "fish", "muc": "squid", "nghieu": "clam", "so diep": "scallop",
}


def fold(value: str) -> str:
    # NFD does not split "đ", so map it explicitly ("đậu" -> "dau").
    value = value.casefold().replace("đ", "d")
    return "".join(char for char in unicodedata.normalize("NFD", value) if not unicodedata.combining(char)).strip()


def query_tokens(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", fold(value), flags=re.UNICODE)


def vietnamese_to_english(value: str) -> str:
    """Replace known Vietnamese food words in accent-folded text, longest phrase first."""
    for vietnamese, english in sorted(VI_FOOD_TERMS.items(), key=lambda item: -len(item[0])):
        value = re.sub(r"(?<!\w)" + vietnamese + r"(?!\w)", english, value)
    return value


def parse_filters(value: dict[str, Any]) -> dict[str, Any]:
    """One validation path for HTTP search and chat retrieval preferences."""
    if not isinstance(value, dict):
        raise ValueError("filters must be an object")
    result: dict[str, Any] = {}
    for key in ("q", "country", "category", "difficulty", "ingredient"):
        item = value.get(key, "")
        if not isinstance(item, str) or len(item) > 200:
            raise ValueError(f"{key} must be a string of at most 200 characters")
        result[key] = item.strip()
    minutes = value.get("max_minutes")
    if minutes in (None, ""):
        result["max_minutes"] = None
    else:
        if isinstance(minutes, bool) or not re.fullmatch(r"\d{1,5}", str(minutes)):
            raise ValueError("max_minutes must be a nonnegative integer")
        result["max_minutes"] = int(minutes)
    exclusions = value.get("exclude_ingredients", [])
    if not isinstance(exclusions, list) or len(exclusions) > 40 or any(not isinstance(item, str) or not item.strip() or len(item) > 100 for item in exclusions):
        raise ValueError("exclude_ingredients must contain at most 40 nonempty strings (100 characters each)")
    folded = [fold(item) for item in exclusions]
    # Also exclude the English name ("sữa" -> "milk"): most source ingredient lists are English.
    result["exclude_ingredients"] = list(dict.fromkeys([*folded, *(vietnamese_to_english(item)[:100] for item in folded)]))
    declared = value.get("require_allergens", False)
    if not isinstance(declared, bool):
        raise ValueError("require_allergens must be a boolean")
    result["require_allergens"] = declared
    sort = value.get("sort", "title")
    if sort not in {"title", "time"}:
        raise ValueError("sort must be title or time")
    result["sort"] = sort
    return result


class KnowledgeBase:
    """SQLite recipe store with relational filters and a Unicode FTS5 index."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS recipes (
                    record_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL, title_folded TEXT NOT NULL,
                    country TEXT NOT NULL, difficulty TEXT NOT NULL,
                    total_minutes INTEGER, allergen_count INTEGER NOT NULL,
                    exclusion_text TEXT NOT NULL, source_name TEXT NOT NULL,
                    payload TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS recipes_country ON recipes(country);
                CREATE INDEX IF NOT EXISTS recipes_time ON recipes(total_minutes);
                CREATE TABLE IF NOT EXISTS categories (
                    record_id TEXT NOT NULL REFERENCES recipes(record_id) ON DELETE CASCADE,
                    name TEXT NOT NULL, PRIMARY KEY(record_id, name)
                );
                CREATE INDEX IF NOT EXISTS categories_name ON categories(name);
                CREATE TABLE IF NOT EXISTS ingredients (
                    record_id TEXT NOT NULL REFERENCES recipes(record_id) ON DELETE CASCADE,
                    name TEXT NOT NULL, PRIMARY KEY(record_id, name)
                );
                CREATE INDEX IF NOT EXISTS ingredients_name ON ingredients(name);
                CREATE VIRTUAL TABLE IF NOT EXISTS recipe_fts USING fts5(
                    record_id UNINDEXED, title, description, country, categories, ingredients,
                    tokenize='unicode61 remove_diacritics 2'
                );
                CREATE TABLE IF NOT EXISTS chat_sessions (
                    session_id TEXT PRIMARY KEY, updated_at REAL NOT NULL, context TEXT NOT NULL
                );
            """)
            if db.execute("PRAGMA user_version").fetchone()[0] < INDEX_VERSION:
                # Older rows were folded differently; an empty payload makes the next import rewrite them.
                db.execute("UPDATE recipes SET payload=''")
                db.execute(f"PRAGMA user_version={INDEX_VERSION}")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        try:
            with db:
                yield db
        finally:
            db.close()

    def import_records(self, records: list[dict[str, Any]], replace: bool = False) -> dict[str, int]:
        # Validate the entire batch before mutating the database. A malformed
        # processed file cannot leave a half-imported knowledge base.
        checked = [validate_recipe(record) for record in records]
        if len({record["record_id"] for record in checked}) != len(checked):
            raise ValueError("The import contains duplicate record IDs")
        report = {"inserted": 0, "updated": 0, "unchanged": 0, "removed": 0}
        with self.connect() as db:
            if replace:
                keep = {record["record_id"] for record in checked}
                stale = [row[0] for row in db.execute("SELECT record_id FROM recipes") if row[0] not in keep]
                for record_id in stale:
                    db.execute("DELETE FROM recipe_fts WHERE record_id=?", (record_id,))
                    db.execute("DELETE FROM recipes WHERE record_id=?", (record_id,))
                report["removed"] = len(stale)
            for record in checked:
                record_id = record["record_id"]
                payload = json.dumps(record, ensure_ascii=False, sort_keys=True)
                previous = db.execute("SELECT payload FROM recipes WHERE record_id=?", (record_id,)).fetchone()
                if previous and previous["payload"] == payload:
                    report["unchanged"] += 1
                    continue
                report["updated" if previous else "inserted"] += 1
                exclusion_text = fold(" ".join([*(f"{item['name']} {item['original_text']}" for item in record["ingredients"]), *record["allergens"]]))
                # Vietnamese-language records also match English exclusions ("sữa" -> "milk").
                exclusion_text += " " + vietnamese_to_english(exclusion_text)
                ingredient_text = fold(" ".join(item["name"] for item in record["ingredients"]))
                db.execute("""
                    INSERT INTO recipes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(record_id) DO UPDATE SET title=excluded.title,
                    title_folded=excluded.title_folded, country=excluded.country,
                    difficulty=excluded.difficulty, total_minutes=excluded.total_minutes,
                    allergen_count=excluded.allergen_count, exclusion_text=excluded.exclusion_text,
                    source_name=excluded.source_name, payload=excluded.payload
                """, (record_id, record["title"], fold(record["title"]), record["country_or_region"], record["difficulty"], record["total_minutes"], len(record["allergens"]), exclusion_text, record["source_name"], payload))
                db.execute("DELETE FROM categories WHERE record_id=?", (record_id,))
                db.execute("DELETE FROM ingredients WHERE record_id=?", (record_id,))
                db.execute("DELETE FROM recipe_fts WHERE record_id=?", (record_id,))
                db.executemany("INSERT INTO categories VALUES (?, ?)", [(record_id, name) for name in set(record["categories"])])
                db.executemany("INSERT INTO ingredients VALUES (?, ?)", [(record_id, name) for name in {fold(item["name"]) for item in record["ingredients"]}])
                # Index folded text so "đ" matches "d" the same way queries are folded.
                db.execute("INSERT INTO recipe_fts VALUES (?, ?, ?, ?, ?, ?)", (record_id, fold(record["title"]), fold(record["description"]), fold(record["country_or_region"]), fold(" ".join(record["categories"])), ingredient_text + " " + vietnamese_to_english(ingredient_text)))
        return report

    def import_processed(self, processed_dir: Path) -> dict[str, int]:
        records = []
        paths = sorted((processed_dir / "recipes").glob("*/*.json"))
        report_path = processed_dir / "quality_report.json"
        if report_path.exists():
            manifest = json.loads(report_path.read_text(encoding="utf-8")).get("processed_files")
            if manifest is not None:
                if not isinstance(manifest, list) or any(not isinstance(item, str) for item in manifest):
                    raise ValueError("Invalid processed_files manifest")
                paths = [(processed_dir / item).resolve() for item in manifest]
                if any(not path.is_relative_to((processed_dir / "recipes").resolve()) or path.suffix != ".json" for path in paths):
                    raise ValueError("Processed manifest paths must stay inside recipes/")
        for path in paths:
            try:
                records.append(validate_recipe(json.loads(path.read_text(encoding="utf-8"))))
            except (OSError, ValueError, TypeError) as exc:
                raise ValueError(f"Cannot index {path.name}: {exc}") from exc
        return {"files": len(records), **self.import_records(records, replace=True)}

    def recipe(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM recipes WHERE record_id=?", (record_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    @staticmethod
    def _where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        terms = query_tokens(filters["q"])
        if filters["q"] and not terms:
            clauses.append("0")
        elif terms:
            clauses.append("r.record_id IN (SELECT record_id FROM recipe_fts WHERE recipe_fts MATCH ?)")
            # Quote each token. User punctuation/operators are never executable
            # FTS syntax, and all SQL values are bound parameters.
            values.append(" AND ".join(f'"{term}"*' for term in terms))
        for key, column in (("country", "country"), ("difficulty", "difficulty")):
            if filters[key]:
                clauses.append(f"r.{column}=?")
                values.append(filters[key])
        if filters["category"]:
            clauses.append("EXISTS (SELECT 1 FROM categories c WHERE c.record_id=r.record_id AND c.name=?)")
            values.append(filters["category"])
        if filters["ingredient"]:
            clauses.append("EXISTS (SELECT 1 FROM ingredients i WHERE i.record_id=r.record_id AND i.name=?)")
            values.append(fold(filters["ingredient"]))
        if filters["max_minutes"] is not None:
            clauses.append("r.total_minutes IS NOT NULL AND r.total_minutes<=?")
            values.append(filters["max_minutes"])
        if filters["require_allergens"]:
            clauses.append("r.allergen_count>0")
        for term in filters["exclude_ingredients"]:
            clauses.append("instr(r.exclusion_text, ?)=0")
            values.append(term)
        return " AND ".join(clauses) or "1", values

    def search(self, filters: dict[str, Any] | None = None, page: int = 1, page_size: int = 6) -> dict[str, Any]:
        filters = parse_filters(filters or {})
        if type(page) is not int or page < 1 or type(page_size) is not int or not 1 <= page_size <= 100:
            raise ValueError("page must be positive and page_size must be between 1 and 100")
        where, values = self._where(filters)
        order = "r.total_minutes IS NULL, r.total_minutes, " if filters["sort"] == "time" else ""
        order += "r.title_folded, r.record_id"
        with self.connect() as db:
            total = db.execute(f"SELECT count(*) FROM recipes r WHERE {where}", values).fetchone()[0]
            page = min(page, max(1, (total + page_size - 1) // page_size))
            rows = db.execute(f"SELECT payload FROM recipes r WHERE {where} ORDER BY {order} LIMIT ? OFFSET ?", [*values, page_size, (page - 1) * page_size]).fetchall()
        mapped = vietnamese_to_english(fold(filters["q"]))[:200]
        if not total and mapped != fold(filters["q"]):
            # Most source records are English: retry "cà chua" as "tomato".
            return self.search({**filters, "q": mapped}, page, page_size)
        return {"items": [json.loads(row["payload"]) for row in rows], "total": total, "page": page, "page_size": page_size}

    def eligible(self, record_ids: list[str], filters: dict[str, Any]) -> list[dict[str, Any]]:
        # Contextual follow-ups must recheck the current preferences.
        preferences = parse_filters({**filters, "q": ""})
        where, values = self._where(preferences)
        if not record_ids:
            return []
        placeholders = ",".join("?" for _ in record_ids)
        with self.connect() as db:
            rows = db.execute(f"SELECT record_id, payload FROM recipes r WHERE {where} AND r.record_id IN ({placeholders})", [*values, *record_ids]).fetchall()
        found = {row["record_id"]: json.loads(row["payload"]) for row in rows}
        return [found[key] for key in record_ids if key in found]

    def named_in(self, question: str, filters: dict[str, Any]) -> list[dict[str, Any]]:
        """Resolve explicitly named titles across the whole collection."""
        with self.connect() as db:
            titles = db.execute("SELECT record_id, title_folded FROM recipes ORDER BY length(title_folded) DESC, record_id").fetchall()
        ids = [row["record_id"] for row in titles if re.search(r"(?<!\w)" + re.escape(row["title_folded"]) + r"(?!\w)", fold(question))]
        return self.eligible(ids, filters) if ids else []

    def facets(self) -> dict[str, list[str]]:
        with self.connect() as db:
            result = {}
            for key, table, column in (("countries", "recipes", "country"), ("categories", "categories", "name"), ("difficulties", "recipes", "difficulty")):
                result[key] = sorted([row[0] for row in db.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column}<>''")], key=fold)
        return result

    def stats(self) -> dict[str, Any]:
        with self.connect() as db:
            total = db.execute("SELECT count(*) FROM recipes").fetchone()[0]
            sources = dict(db.execute("SELECT source_name, count(*) FROM recipes GROUP BY source_name"))
            regions = dict(db.execute("SELECT country, count(*) FROM recipes GROUP BY country"))
        return {"recipes": total, "sources": sources, "countries_or_regions": regions, "search": "SQLite FTS5"}
