from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from recipehub.config import Settings
from recipehub.text import normalize_recipe_query, normalize_text, tokens


MAX_PAGE_SIZE = 50


def _as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _recipe_search_text(record: dict[str, Any]) -> str:
    ingredients = _as_list(record.get("ingredients"))
    ingredient_text = " ".join(
        f"{item.get('name', '')} {item.get('original_text', '')}"
        for item in ingredients
        if isinstance(item, dict)
    )
    return " ".join(
        str(value or "")
        for value in (
            record.get("title"),
            record.get("description"),
            record.get("country_or_region"),
            " ".join(str(item) for item in _as_list(record.get("categories"))),
            ingredient_text,
        )
    )


def _normalize_record(value: dict[str, Any]) -> dict[str, Any]:
    """Fill safe structural defaults while preserving all source values."""
    record = dict(value)
    record_id = str(record.get("record_id") or "").strip()
    title = str(record.get("title") or record.get("original_title") or "").strip()
    if not record_id or not title:
        raise ValueError("record is missing record_id or title")
    record["record_id"] = record_id
    record["title"] = title
    for key in ("ingredients", "instructions", "categories", "allergens", "tips", "substitutions", "tools"):
        record[key] = _as_list(record.get(key))
    for key in ("country_or_region", "description", "difficulty", "source_name", "source_url", "source_terms_url", "attribution"):
        record[key] = str(record.get(key) or "")
    return record


class KnowledgeBase:
    """SQLite knowledge base loaded from the normalized recipe data lake."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.settings.ensure_directories()
        self.path = self.settings.database_file
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fts_available = True
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                """CREATE TABLE IF NOT EXISTS recipes (
                    record_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    country_or_region TEXT NOT NULL,
                    total_minutes INTEGER,
                    difficulty TEXT NOT NULL,
                    search_text TEXT NOT NULL,
                    record_json TEXT NOT NULL
                )"""
            )
            connection.execute("CREATE INDEX IF NOT EXISTS recipes_region_idx ON recipes(country_or_region)")
            connection.execute("CREATE INDEX IF NOT EXISTS recipes_title_idx ON recipes(title)")
            try:
                connection.execute(
                    """CREATE VIRTUAL TABLE IF NOT EXISTS recipe_search USING fts5(
                        record_id UNINDEXED, title, description, region, categories, ingredients,
                        tokenize='unicode61 remove_diacritics 2'
                    )"""
                )
            except sqlite3.OperationalError:
                self._fts_available = False

    def rebuild(self) -> dict[str, int]:
        """Replace the searchable snapshot from all normalized JSON records."""
        source_files = sorted((self.settings.processed_dir / "recipes").glob("*/*.json"))
        records: list[dict[str, Any]] = []
        skipped = 0
        for path in source_files:
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                records.append(_normalize_record(value))
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                skipped += 1

        with self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            connection.execute("DELETE FROM recipes")
            if self._fts_available:
                connection.execute("DELETE FROM recipe_search")
            for record in records:
                ingredients = _as_list(record.get("ingredients"))
                categories = _as_list(record.get("categories"))
                total_minutes = record.get("total_minutes")
                if not isinstance(total_minutes, int) or isinstance(total_minutes, bool):
                    total_minutes = None
                search_text = _recipe_search_text(record)
                connection.execute(
                    """INSERT OR REPLACE INTO recipes
                    (record_id, title, country_or_region, total_minutes, difficulty, search_text, record_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        record["record_id"], record["title"], record.get("country_or_region", ""),
                        total_minutes, record.get("difficulty", ""), search_text,
                        json.dumps(record, ensure_ascii=False, separators=(",", ":")),
                    ),
                )
                if self._fts_available:
                    connection.execute(
                        """INSERT INTO recipe_search
                        (record_id, title, description, region, categories, ingredients)
                        VALUES (?, ?, ?, ?, ?, ?)""",
                        (
                            record["record_id"], record["title"], record.get("description", ""),
                            record.get("country_or_region", ""),
                            " ".join(str(item) for item in categories),
                            " ".join(
                                f"{item.get('name', '')} {item.get('original_text', '')}"
                                for item in ingredients if isinstance(item, dict)
                            ),
                        ),
                    )
        return {"indexed": len(records), "skipped": skipped}

    @staticmethod
    def _fts_expression(query: str, match_all: bool) -> str:
        query_tokens = tokens(normalize_recipe_query(query))
        joiner = " AND " if match_all else " OR "
        return joiner.join(f'"{token}"' for token in query_tokens)

    def _query_records(self, query: str, match_all: bool) -> list[dict[str, Any]]:
        expression = self._fts_expression(query, match_all)
        if not expression:
            return self.all_records()
        with self._connection() as connection:
            if self._fts_available:
                try:
                    rows = connection.execute(
                        """SELECT recipes.record_json
                        FROM recipe_search JOIN recipes USING(record_id)
                        WHERE recipe_search MATCH ?
                        ORDER BY bm25(recipe_search), recipes.title COLLATE NOCASE, recipes.record_id""",
                        (expression,),
                    ).fetchall()
                    return [json.loads(row[0]) for row in rows]
                except sqlite3.OperationalError:
                    self._fts_available = False
            rows = connection.execute("SELECT record_json, search_text FROM recipes").fetchall()
        query_tokens = tokens(normalize_recipe_query(query))
        matches: list[tuple[int, dict[str, Any]]] = []
        for row in rows:
            normalized = normalize_text(row["search_text"])
            found = [term for term in query_tokens if term in normalized]
            if (len(found) == len(query_tokens) if match_all else bool(found)):
                matches.append((-len(found), json.loads(row["record_json"])))
        matches.sort(key=lambda item: (item[0], normalize_text(item[1].get("title", "")), item[1].get("record_id", "")))
        return [record for _, record in matches]

    def all_records(self) -> list[dict[str, Any]]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT record_json FROM recipes ORDER BY title COLLATE NOCASE, record_id"
            ).fetchall()
        return [json.loads(row[0]) for row in rows]

    @staticmethod
    def _matches_filters(record: dict[str, Any], filters: dict[str, Any]) -> bool:
        if filters.get("country") and normalize_recipe_query(record.get("country_or_region", "")) != normalize_recipe_query(str(filters["country"])):
            return False
        if filters.get("category") and normalize_recipe_query(str(filters["category"])) not in {
            normalize_recipe_query(str(item)) for item in _as_list(record.get("categories"))
        }:
            return False
        if filters.get("difficulty") and normalize_recipe_query(record.get("difficulty", "")) != normalize_recipe_query(str(filters["difficulty"])):
            return False
        max_minutes = filters.get("max_minutes")
        if max_minutes not in (None, ""):
            try:
                ceiling = int(max_minutes)
            except (TypeError, ValueError):
                return False
            total = record.get("total_minutes")
            if not isinstance(total, int) or isinstance(total, bool) or total > ceiling:
                return False
        if filters.get("require_allergens") and not _as_list(record.get("allergens")):
            return False
        exclusions = filters.get("exclude_ingredients", [])
        if isinstance(exclusions, str):
            exclusions = [exclusions]
        excluded_terms: list[str] = []
        for item in exclusions:
            normalized = normalize_recipe_query(str(item))
            if not normalized:
                continue
            excluded_terms.append(normalized)
            if normalized.endswith("s") and len(normalized) > 3:
                excluded_terms.append(normalized[:-1])
        if excluded_terms:
            ingredients = _as_list(record.get("ingredients"))
            searchable = " ".join(
                [
                    *(str(item) for item in _as_list(record.get("allergens"))),
                    *(f"{item.get('name', '')} {item.get('original_text', '')}"
                      for item in ingredients if isinstance(item, dict)),
                ]
            )
            searchable = normalize_recipe_query(searchable)
            if any(term in searchable for term in excluded_terms):
                return False
        return True

    def matching_records(
        self,
        filters: dict[str, Any] | None = None,
        query: str = "",
        match_all: bool = True,
    ) -> list[dict[str, Any]]:
        active_filters = filters or {}
        records = self._query_records(query, match_all) if query.strip() else self.all_records()
        records = [record for record in records if self._matches_filters(record, active_filters)]
        sort_mode = active_filters.get("sort", "title")
        if sort_mode == "time":
            records.sort(key=lambda record: (
                record.get("total_minutes") is None,
                record.get("total_minutes") or 0,
                normalize_text(record.get("title", "")),
                record.get("record_id", ""),
            ))
        else:
            records.sort(key=lambda record: (normalize_text(record.get("title", "")), record.get("record_id", "")))
        return records

    def search(
        self,
        filters: dict[str, Any] | None = None,
        query: str = "",
        page: int = 1,
        page_size: int = 6,
        match_all: bool = True,
    ) -> dict[str, Any]:
        records = self.matching_records(filters, query, match_all)
        total = len(records)
        page_size = max(1, min(int(page_size), MAX_PAGE_SIZE))
        pages = max(1, (total + page_size - 1) // page_size)
        page = min(max(1, int(page)), pages)
        start = (page - 1) * page_size
        return {"items": records[start:start + page_size], "total": total, "page": page, "page_size": page_size}

    def get(self, record_id: str) -> dict[str, Any] | None:
        with self._connection() as connection:
            row = connection.execute("SELECT record_json FROM recipes WHERE record_id = ?", (record_id,)).fetchone()
        return json.loads(row[0]) if row else None

    def facets(self) -> dict[str, list[str]]:
        countries: set[str] = set()
        categories: set[str] = set()
        difficulties: set[str] = set()
        for record in self.all_records():
            if record.get("country_or_region"):
                countries.add(str(record["country_or_region"]))
            categories.update(str(item) for item in _as_list(record.get("categories")) if str(item).strip())
            if record.get("difficulty"):
                difficulties.add(str(record["difficulty"]))
        key = lambda item: (normalize_text(item), item)
        return {
            "countries": sorted(countries, key=key),
            "categories": sorted(categories, key=key),
            "difficulties": sorted(difficulties, key=key),
        }

    def count(self) -> int:
        with self._connection() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM recipes").fetchone()[0])
