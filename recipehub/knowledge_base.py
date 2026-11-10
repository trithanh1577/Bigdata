from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from recipehub.models import validate_recipe
from recipehub.ingestion_lock import ingestion_lock
from recipehub.seed import load_seed, merge_recipe_records
from recipehub.text import culinary_query_groups, ingredient_exclusion_terms, normalize_recipe_query


def fold(value: str) -> str:
    return "".join(char for char in unicodedata.normalize("NFD", value.casefold()) if not unicodedata.combining(char)).strip()


def query_tokens(value: str) -> list[str]:
    return re.findall(r"[^\W_]+", fold(value), flags=re.UNICODE)


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
    if not isinstance(exclusions, list) or len(exclusions) > 20 or any(not isinstance(item, str) or not item.strip() or len(item) > 100 for item in exclusions):
        raise ValueError("exclude_ingredients must contain at most 20 nonempty strings (100 characters each)")
    result["exclude_ingredients"] = list(dict.fromkeys(fold(item) for item in exclusions))
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

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=15)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.create_function("regexp", 2, lambda pattern, text: re.search(pattern, text) is not None, deterministic=True)
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
                db.execute("INSERT INTO recipe_fts VALUES (?, ?, ?, ?, ?, ?)", (record_id, record["title"], record["description"], record["country_or_region"], " ".join(record["categories"]), " ".join(item["name"] for item in record["ingredients"])))
        return report

    def import_seed(self, path: Path) -> dict[str, int]:
        records = load_seed(path)
        with self.connect() as db:
            existing = [json.loads(row["payload"]) for row in db.execute("SELECT payload FROM recipes")]
        # Restore a bundled baseline without deleting other collected dishes or
        # overwriting a newer source version already present on the server.
        merged = merge_recipe_records(existing, records)
        return {"files": len(records), **self.import_records(merged)}

    def import_processed(self, processed_dir: Path, seed_file: Path | None = None) -> dict[str, int]:
        # Readers must see one complete publication of files and its manifest,
        # including when the scheduler and chat ingestion run in other processes.
        with ingestion_lock(processed_dir):
            return self._import_processed(processed_dir, seed_file)

    def _import_processed(self, processed_dir: Path, seed_file: Path | None) -> dict[str, int]:
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
        if seed_file is not None and seed_file.exists():
            seeds = load_seed(seed_file)
            with self.connect() as db:
                existing = [json.loads(row["payload"]) for row in db.execute("SELECT payload FROM recipes")]
            # Future crawls must retain the bundled recipes even when this
            # deployment has no corresponding raw/processed files yet.
            merged = merge_recipe_records(existing, seeds, records)
            return {"files": len(records), "seed_recipes": len(seeds), **self.import_records(merged)}
        return {"files": len(records), **self.import_records(records, replace=True)}

    def recipe(self, record_id: str) -> dict[str, Any] | None:
        with self.connect() as db:
            row = db.execute("SELECT payload FROM recipes WHERE record_id=?", (record_id,)).fetchone()
        return json.loads(row["payload"]) if row else None

    @staticmethod
    def _where(filters: dict[str, Any]) -> tuple[str, list[Any]]:
        clauses: list[str] = []
        values: list[Any] = []
        groups = culinary_query_groups(filters["q"])
        if filters["q"] and not groups:
            clauses.append("0")
        elif groups:
            clauses.append("r.record_id IN (SELECT record_id FROM recipe_fts WHERE recipe_fts MATCH ?)")
            # Each phrase can match its source wording OR a known translation;
            # groups still combine with AND, preserving multi-term searches.
            # Tokens are quoted and bound, so user input cannot execute FTS syntax.
            values.append(" AND ".join(
                "(" + " OR ".join(
                    "(" + " AND ".join(
                        f'"{term}"' + ("*" if index == 0 or variant == normalize_recipe_query(variant) else "")
                        for term in query_tokens(variant)
                    ) + ")"
                    for index, variant in enumerate(variants)
                ) + ")"
                for variants in groups
            ))
        for key, column in (("country", "country"), ("difficulty", "difficulty")):
            if filters[key]:
                clauses.append(f"r.{column}=?")
                values.append(filters[key])
        if filters["category"]:
            clauses.append("EXISTS (SELECT 1 FROM categories c WHERE c.record_id=r.record_id AND c.name=?)")
            values.append(filters["category"])
        if filters["ingredient"]:
            ingredient_names = list(dict.fromkeys(fold(term) for term in ingredient_exclusion_terms(filters["ingredient"])))
            placeholders = ",".join("?" for _ in ingredient_names)
            clauses.append(f"EXISTS (SELECT 1 FROM ingredients i WHERE i.record_id=r.record_id AND i.name IN ({placeholders}))")
            values.extend(ingredient_names)
        if filters["max_minutes"] is not None:
            clauses.append("r.total_minutes IS NOT NULL AND r.total_minutes<=?")
            values.append(filters["max_minutes"])
        if filters["require_allergens"]:
            clauses.append("r.allergen_count>0")
        for term in filters["exclude_ingredients"]:
            aliases = list(dict.fromkeys(fold(item) for item in ingredient_exclusion_terms(term)))
            for alias in aliases:
                if alias == term and (len(term) > 3 or len(aliases) == 1):
                    clauses.append("instr(r.exclusion_text, ?)=0")
                    values.append(alias)
                else:
                    # Short aliases such as Vietnamese "lạc" must not match
                    # unrelated words such as "black" in "black pepper".
                    clauses.append("r.exclusion_text NOT REGEXP ?")
                    compound = len(alias) >= 4 and alias == normalize_recipe_query(alias)
                    values.append(r"(?<!\w)" + re.escape(alias) + ("" if compound else r"(?!\w)"))
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
