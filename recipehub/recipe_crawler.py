from __future__ import annotations

import json
import re
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote, urlsplit

import requests

from recipehub.config import Settings
from recipehub.text import stable_id


RawRecord = tuple[str, str, dict[str, Any], dict[str, Any]]
CONTACT_RE = re.compile(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|https?://[^\s;)]+", re.IGNORECASE)
PLACEHOLDER_CONTACT_RE = re.compile(
    r"your[-_ ]?(?:email|url|project)|replace[-_ ]?me|example\.(?:com|org|net)",
    re.IGNORECASE,
)


class RecipeCrawler:
    """Person 1's source adapters; raw API responses are saved before normalization."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.settings.ensure_directories()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.settings.user_agent})

    def _get_json(self, url: str, params: dict[str, object] | None = None) -> dict[str, Any]:
        for attempt in range(4):
            try:
                response = self.session.get(url, params=params, timeout=self.settings.timeout_seconds)
            except (requests.Timeout, requests.ConnectionError):
                if attempt == 3:
                    raise
                time.sleep(min(30.0, 2**attempt))
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt == 3:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After", "")
                try:
                    wait = float(retry_after)
                except ValueError:
                    try:
                        wait = max(
                            1.0,
                            (parsedate_to_datetime(retry_after) - datetime.now(timezone.utc)).total_seconds(),
                        )
                    except (TypeError, ValueError, OverflowError):
                        wait = 2**attempt
                time.sleep(min(30.0, max(1.0, wait)))
                continue

            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                raise ValueError(f"Expected a JSON object from {url}")
            time.sleep(self.settings.delay_seconds)
            return payload
        raise RuntimeError("HTTP retry loop ended unexpectedly")

    def crawl(self, max_items_per_source: int = 20) -> dict[str, Any]:
        if max_items_per_source < 1:
            raise ValueError("max_items_per_source must be at least 1")
        state = self._load_state()
        run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        report: dict[str, Any] = {
            "run_id": run_id,
            "sources": 0,
            "fetched": 0,
            "raw_saved": 0,
            "failed": 0,
            "errors": [],
        }
        for source in self.settings.load_sources():
            report["sources"] += 1
            source_id = str(source["id"])
            run_dir = self.settings.raw_dir / source_id / "runs" / run_id
            records_dir = run_dir / "records"
            records_dir.mkdir(parents=True, exist_ok=True)
            source_summary: dict[str, Any] = {"run_id": run_id, "source_id": source_id, "fetched": 0, "raw_saved": 0}
            try:
                source_cursor = state.get(source_id, {})
                if not isinstance(source_cursor, dict):
                    source_cursor = {}
                if source.get("type") == "themealdb":
                    records, next_cursor = self._themealdb_records(
                        source, max_items_per_source, source_cursor
                    )
                elif source.get("type") == "wikibooks":
                    records, next_cursor = self._wikibooks_records(
                        source, max_items_per_source, source_cursor
                    )
                else:
                    raise ValueError(f"Unknown source type: {source.get('type')}")

                for source_record_id, source_url, payload, extra in records:
                    public_extra = {key: value for key, value in extra.items() if not key.startswith("_")}
                    collected_at = datetime.now(timezone.utc).isoformat()
                    envelope = {
                        "source_id": source_id,
                        "source_name": str(source["name"]),
                        "source_record_id": source_record_id,
                        "source_url": source_url,
                        "source_license": str(source.get("license", "Check provider terms")),
                        "source_terms_url": str(source.get("terms_url", "")),
                        "attribution": str(source.get("attribution", source["name"])),
                        "language": str(source.get("language", "")),
                        "collected_at": collected_at,
                        "payload": payload,
                        **public_extra,
                    }
                    filename = f"{stable_id(source_record_id)}.json"
                    raw_path = records_dir / filename
                    raw_path.write_text(
                        json.dumps(envelope, ensure_ascii=False, indent=2), encoding="utf-8"
                    )
                    report["fetched"] += 1
                    report["raw_saved"] += 1
                    source_summary["fetched"] += 1
                    source_summary["raw_saved"] += 1
                    manifest_entry = {
                        "run_id": run_id,
                        "source_id": source_id,
                        "source_name": str(source["name"]),
                        "source_record_id": source_record_id,
                        "url": source_url,
                        "collected_at": collected_at,
                        "raw_file": raw_path.relative_to(self.settings.project_root).as_posix(),
                    }
                    with self._manifest_file().open("a", encoding="utf-8", newline="\n") as manifest:
                        manifest.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")

                state[source_id] = next_cursor
                self._save_state(state)
            except (requests.RequestException, ValueError, KeyError, TypeError, OSError) as exc:
                report["failed"] += 1
                error = f"{type(exc).__name__}: {exc}"
                report["errors"].append({"source": source_id, "error": error})
                source_summary["error"] = error

            (run_dir / "run.json").write_text(
                json.dumps(source_summary, ensure_ascii=False, indent=2), encoding="utf-8"
            )

        return report

    def _state_file(self):
        return self.settings.state_dir / "crawl_cursors.json"

    def _manifest_file(self):
        return self.settings.state_dir / "crawl_manifest.jsonl"

    def _load_state(self) -> dict[str, Any]:
        path = self._state_file()
        if not path.exists():
            return {}
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Cannot read crawler cursor state at {path}: {exc}") from exc
        if not isinstance(state, dict):
            raise ValueError(f"Crawler cursor state at {path} must contain a JSON object")
        return state

    def _save_state(self, state: dict[str, Any]) -> None:
        path = self._state_file()
        temporary_path = path.with_suffix(".tmp")
        temporary_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        temporary_path.replace(path)

    @staticmethod
    def _object_list(payload: dict[str, Any], key: str, label: str) -> list[dict[str, Any]]:
        value = payload.get(key)
        if value is None:
            return []
        if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
            raise ValueError(f"Expected {label}.{key} to be a list of JSON objects")
        return value

    def _themealdb_records(
        self, source: dict[str, object], limit: int, cursor: dict[str, Any] | None = None
    ) -> tuple[list[RawRecord], dict[str, Any]]:
        base_url = str(source["base_url"]).rstrip("/")
        api_key = str(source.get("api_key", "1"))
        cursor = cursor or {}
        area_cursors = cursor.get("areas", {})
        if not isinstance(area_cursors, dict):
            area_cursors = {}
        meals_by_id: dict[str, str] = {}
        area_list = self._get_json(f"{base_url}/{api_key}/list.php", {"a": "list"})
        area_items = self._object_list(area_list, "meals", "TheMealDB area-list response")
        available_areas = {
            str(item.get("strArea", "")).casefold(): str(item.get("strArea", ""))
            for item in area_items
        }
        configured_area_value = source.get("areas", [])
        if not isinstance(configured_area_value, list):
            raise ValueError("TheMealDB source configuration 'areas' must be a JSON list")
        configured_areas = [str(area) for area in configured_area_value]
        areas = [available_areas[area.casefold()] for area in configured_areas if area.casefold() in available_areas]
        if not areas:
            raise ValueError(f"No configured areas are available from TheMealDB: {configured_areas}")
        meals_by_area: dict[str, list[dict[str, Any]]] = {}
        for area in areas:
            response = self._get_json(f"{base_url}/{api_key}/filter.php", {"a": str(area)})
            filter_meals = self._object_list(response, "meals", "TheMealDB filter response")
            candidates = [meal for meal in filter_meals if meal.get("idMeal")]
            last_id = str(area_cursors.get(str(area), ""))
            last_index = next(
                (index for index, meal in enumerate(candidates) if str(meal["idMeal"]) == last_id),
                None,
            )
            start = (last_index + 1) % len(candidates) if last_index is not None and candidates else 0
            meals_by_area[str(area)] = candidates[start:] + candidates[:start]

        # Round-robin configured areas so a small PoC crawl represents several
        # cuisines; persist the last ID per area to keep later scheduled runs
        # moving through the available collection rather than repeating page 1.
        next_area_cursors = dict(area_cursors)
        while len(meals_by_id) < max(1, limit) and any(meals_by_area.values()):
            for area in areas:
                candidates = meals_by_area[str(area)]
                if candidates:
                    meal = candidates.pop(0)
                    meal_id = str(meal["idMeal"])
                    next_area_cursors[str(area)] = meal_id
                    # Keep the area from the request because the filter
                    # endpoint does not always include strArea in its results.
                    meals_by_id.setdefault(meal_id, str(area))
                    if len(meals_by_id) >= max(1, limit):
                        break

        records: list[RawRecord] = []
        for meal_id, area in list(meals_by_id.items())[:limit]:
            response = self._get_json(f"{base_url}/{api_key}/lookup.php", {"i": meal_id})
            meal_list = self._object_list(response, "meals", "TheMealDB lookup response")
            if not meal_list:
                continue
            meal = meal_list[0]
            records.append((
                meal_id,
                f"https://www.themealdb.com/meal/{meal_id}",
                meal,
                {"language": "en", "_cursor_area": area, "_cursor_id": meal_id},
            ))
        return records, {"areas": next_area_cursors}

    def _wikibooks_records(
        self, source: dict[str, object], limit: int, cursor: dict[str, Any] | None = None
    ) -> tuple[list[RawRecord], dict[str, Any]]:
        api_url = str(source["api_url"])
        if urlsplit(api_url).hostname == "en.wikibooks.org" and not self._has_contactable_user_agent():
            raise ValueError(
                "Wikibooks requires a descriptive User-Agent with a real contact email or project URL. "
                "Set CRAWLER_USER_AGENT in .env before crawling."
            )

        cursor = cursor or {}
        continuation = cursor.get("cmcontinue")
        records: list[RawRecord] = []
        while len(records) < limit:
            remaining = max(1, limit - len(records))
            params: dict[str, object] = {
                "action": "query",
                "list": "categorymembers",
                "cmtitle": str(source.get("category", "Category:Recipes")),
                "cmnamespace": 0,
                "cmprop": "ids|title",
                "cmsort": "timestamp",
                "cmdir": "desc",
                "cmlimit": min(remaining, 500),
                "format": "json",
                "formatversion": 2,
            }
            if continuation:
                params["cmcontinue"] = str(continuation)
            listing = self._get_json(api_url, params)
            query = listing.get("query", {})
            continuation_data = listing.get("continue", {})
            if query is None:
                query = {}
            if continuation_data is None:
                continuation_data = {}
            if not isinstance(query, dict):
                raise ValueError("Wikibooks response field 'query' must be a JSON object")
            if not isinstance(continuation_data, dict):
                raise ValueError("Wikibooks response field 'continue' must be a JSON object")
            members = self._object_list(query, "categorymembers", "Wikibooks query response")
            next_continuation = continuation_data.get("cmcontinue")
            for member in members:
                title = str(member.get("title", ""))
                if not title.startswith("Cookbook:"):
                    continue
                page = self._get_json(api_url, {
                    "action": "parse",
                    "page": title,
                    "prop": "text|categories|displaytitle",
                    "redirects": 1,
                    "format": "json",
                })
                parsed = page.get("parse")
                if parsed is None:
                    continue
                if not isinstance(parsed, dict):
                    raise ValueError("Wikibooks response field 'parse' must be a JSON object")
                if not parsed:
                    continue
                page_id = str(parsed.get("pageid") or member.get("pageid") or title)
                url_title = quote(title.replace(" ", "_"), safe="()/:,_-')")
                records.append((
                    page_id,
                    f"https://en.wikibooks.org/wiki/{url_title}",
                    page,
                    {"title": title, "language": str(source.get("language", "en"))},
                ))
                if len(records) >= limit:
                    break
            continuation = next_continuation
            if not continuation:
                break
        return records, {"cmcontinue": continuation}

    def _has_contactable_user_agent(self) -> bool:
        agent = self.settings.user_agent
        if PLACEHOLDER_CONTACT_RE.search(agent):
            return False
        return bool(CONTACT_RE.search(agent))
