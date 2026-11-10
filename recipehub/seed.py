from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from recipehub.config import Settings
from recipehub.models import validate_recipe


SEED_FORMAT_VERSION = 1


def seed_path(settings: Settings) -> Path:
    return settings.project_root / "seed" / "recipes.json"


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result


def _reject_nonfinite(value: str) -> None:
    raise ValueError("Recipe JSON must not contain NaN or infinity")


def _read_json(value: str) -> Any:
    return json.loads(value, object_pairs_hook=_unique_object, parse_constant=_reject_nonfinite)


def _validated_records(records: Any) -> list[dict[str, Any]]:
    if not isinstance(records, list) or not records:
        raise ValueError("A seed bundle must contain at least one recipe")
    checked = [validate_recipe(record) for record in records]
    if len({record["record_id"] for record in checked}) != len(checked):
        raise ValueError("The seed bundle contains duplicate recipe IDs")
    return sorted(checked, key=lambda record: record["record_id"])


def _timestamp(value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError, OverflowError):
        return datetime.min.replace(tzinfo=timezone.utc)


def merge_recipe_records(*batches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep the newest source snapshot for each ID, preferring later batches on ties."""
    records: dict[str, dict[str, Any]] = {}
    versions: dict[str, tuple[datetime, datetime]] = {}
    for batch in batches:
        for raw in batch:
            record = validate_recipe(raw)
            record_id = record["record_id"]
            version = (_timestamp(record["collected_at"]), _timestamp(record["processed_at"]))
            if record_id not in versions or version >= versions[record_id]:
                records[record_id] = record
                versions[record_id] = version
    return [records[record_id] for record_id in sorted(records)]


def load_seed(path: Path) -> list[dict[str, Any]]:
    """Validate the entire portable recipe bundle before a caller imports it."""
    value = _read_json(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("The seed bundle must be a JSON object")
    if type(value.get("format_version")) is not int or value["format_version"] != SEED_FORMAT_VERSION:
        raise ValueError("Expected seed format_version 1")
    allowed = {"format_version", "recipe_count", "recipes", "exported_at"}
    if value.keys() - allowed:
        raise ValueError("The seed bundle contains unknown fields")
    count = value.get("recipe_count")
    if type(count) is not int or count < 1:
        raise ValueError("Seed recipe_count must be a positive integer")
    records = _validated_records(value.get("recipes"))
    if count != len(records):
        raise ValueError("Seed recipe_count does not match the recipe array")
    if "exported_at" in value and not isinstance(value["exported_at"], str):
        raise ValueError("Seed exported_at must be a string")
    return records


def export_seed(settings: Settings, output: Path | None = None) -> dict[str, Any]:
    """Export recipe payloads only; never open the source database for writing."""
    database = settings.database_path.resolve()
    target = (Path(output) if output is not None else seed_path(settings)).resolve()
    if target == database:
        raise ValueError("The seed output must not replace the recipe database")
    if target.suffix.lower() != ".json":
        raise ValueError("The seed output must be a .json file")
    if not database.is_file():
        raise ValueError("No recipe database exists. Collect and build recipes before exporting.")
    try:
        with closing(sqlite3.connect(database.as_uri() + "?mode=ro", uri=True, timeout=15)) as db:
            rows = db.execute("SELECT payload FROM recipes ORDER BY record_id").fetchall()
    except sqlite3.Error as exc:
        raise ValueError("Cannot read recipes from the source database") from exc
    records = _validated_records([_read_json(row[0]) for row in rows])
    bundle = {
        "format_version": SEED_FORMAT_VERSION,
        "recipe_count": len(records),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "recipes": records,
    }
    # Serialize fully before opening a temporary output, so invalid nested
    # values cannot replace a previously exported, working seed bundle.
    content = json.dumps(bundle, ensure_ascii=False, allow_nan=False, indent=2) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, prefix=f".{target.name}.", suffix=".tmp", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return {"output": str(target), "recipe_count": len(records)}
