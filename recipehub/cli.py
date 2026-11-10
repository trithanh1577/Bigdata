from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any

from recipehub.config import Settings
from recipehub.ingestion_lock import ingestion_lock
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler
from recipehub.knowledge_base import KnowledgeBase
from recipehub.seed import export_seed, seed_path


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def _stats(settings: Settings) -> dict[str, Any]:
    processed_files = list((settings.processed_dir / "recipes").glob("*/*.json"))
    countries: dict[str, int] = {}
    for path in processed_files:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        country = record.get("country_or_region") or "Unknown"
        countries[country] = countries.get(country, 0) + 1
    return {
        "raw_records": len(list(settings.raw_dir.glob("*/runs/*/records/*.json"))),
        "processed_records": len(processed_files),
        "countries_or_regions": countries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Culinary Knowledge Base — ingestion, search, API, and website")
    commands = parser.add_subparsers(dest="command", required=True)
    crawl = commands.add_parser("crawl", help="Collect source records into the raw data lake")
    crawl.add_argument("--max-items", type=_positive_int, default=20, help="Maximum recipes per source per run")
    crawl.add_argument("--source", action="append", help="Only crawl this configured source ID; repeat to select more")
    normalize = commands.add_parser("normalize", help="Normalize raw source records into the processed data lake")
    schedule = commands.add_parser("schedule", help="Crawl, normalize, and index on a repeating interval")
    interval = schedule.add_mutually_exclusive_group()
    interval.add_argument("--days", type=_positive_int, help="Days between runs; defaults to once per day")
    interval.add_argument("--minutes", type=_positive_int, help="Minutes between runs, for example --minutes 5")
    schedule.add_argument("--max-items", type=_positive_int, default=20, help="Maximum recipes per source per run")
    commands.add_parser("stats", help="Show raw/processed counts and country coverage")
    commands.add_parser("build", aliases=["index"], help="Build or refresh the SQLite knowledge base from processed recipes")
    export = commands.add_parser("export-seed", help="Export indexed recipes to the Git-tracked deployment dataset")
    export.add_argument("--output", type=Path, help="Output JSON path; defaults to seed/recipes.json")
    restore = commands.add_parser("import-seed", help="Merge a deployment dataset into SQLite without deleting recipes")
    restore.add_argument("--input", type=Path, help="Input JSON path; defaults to seed/recipes.json")
    pipeline = commands.add_parser("pipeline", help="Crawl, normalize, and synchronize the knowledge base")
    pipeline.add_argument("--max-items", type=_positive_int, default=20)
    server = commands.add_parser("serve", help="Serve the connected website and HTTP API")
    server.add_argument("--host", default="127.0.0.1")
    server.add_argument("--port", type=_positive_int, default=8000)
    server.add_argument("--allow-origin", action="append", default=None, help="Allowed cross-origin frontend URL; repeat for multiple origins")
    return parser


def _run_pipeline(settings: Settings, max_items: int) -> dict[str, Any]:
    # Keep the snapshot and its database import together. Individual stages
    # also lock when invoked separately; the shared lock is reentrant.
    with ingestion_lock(settings.processed_dir):
        crawl_result = RecipeCrawler(settings).crawl(max_items)
        normalize_result = NormalizationPipeline(settings).run()
        index_result = KnowledgeBase(settings.database_path).import_processed(settings.processed_dir, seed_file=seed_path(settings))
        return {"crawl": crawl_result, "normalize": normalize_result, "index": index_result}


def _prepare_store(settings: Settings) -> KnowledgeBase:
    """Restore the shipped collection before accepting website requests."""
    with ingestion_lock(settings.processed_dir):
        store = KnowledgeBase(settings.database_path)
        bundled = seed_path(settings)
        processed_files = list((settings.processed_dir / "recipes").glob("*/*.json"))
        if processed_files or (settings.processed_dir / "quality_report.json").exists():
            result = store.import_processed(settings.processed_dir, seed_file=bundled)
        elif bundled.exists():
            result = store.import_seed(bundled)
        else:
            return store
        print(json.dumps({"startup_import": result, "recipes": store.stats()["recipes"]}), flush=True)
        return store


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    if args.command == "serve" and args.port > 65535:
        raise SystemExit("port must be between 1 and 65535")
    settings = Settings()
    settings.ensure_directories()

    if args.command == "crawl":
        result = RecipeCrawler(settings).crawl(args.max_items, args.source)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["failed"]:
            raise SystemExit(1)
    elif args.command == "normalize":
        result = NormalizationPipeline(settings).run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["invalid"]:
            raise SystemExit(1)
    elif args.command == "stats":
        result = _stats(settings)
        if settings.database_path.exists():
            result["knowledge_base"] = KnowledgeBase(settings.database_path).stats()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command in {"build", "index"}:
        print(json.dumps(KnowledgeBase(settings.database_path).import_processed(settings.processed_dir, seed_file=seed_path(settings)), ensure_ascii=False, indent=2))
    elif args.command == "export-seed":
        print(json.dumps(export_seed(settings, args.output), ensure_ascii=False, indent=2))
    elif args.command == "import-seed":
        with ingestion_lock(settings.processed_dir):
            result = KnowledgeBase(settings.database_path).import_seed(args.input or seed_path(settings))
        print(json.dumps(result, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        from recipehub.server import serve
        store = _prepare_store(settings)
        serve(store, settings.project_root / "frontend", args.host, args.port, args.allow_origin, settings)
    elif args.command == "pipeline":
        result = _run_pipeline(settings, args.max_items)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["crawl"]["failed"] or result["normalize"]["invalid"]:
            raise SystemExit(1)
    elif args.command == "schedule":
        interval_seconds = args.minutes * 60 if args.minutes else (args.days or 1) * 24 * 60 * 60
        interval_label = f"{args.minutes} minute(s)" if args.minutes else f"{args.days or 1} day(s)"
        print(f"Scheduler: crawl + normalize + index every {interval_label}, starting now. Press Ctrl+C to stop.")
        try:
            while True:
                started = time.monotonic()
                try:
                    result = _run_pipeline(settings, args.max_items)
                    print(json.dumps(result, ensure_ascii=False), flush=True)
                except Exception as exc:  # any failed run (network, parsing, locked file) is retried next interval
                    # A temporary disk/database problem must not silently stop
                    # automatic collection for the remainder of the demo.
                    print(json.dumps({"error": f"{type(exc).__name__}: {exc}", "retry_in_seconds": interval_seconds}, ensure_ascii=False), flush=True)
                time.sleep(max(0, interval_seconds - (time.monotonic() - started)))
        except KeyboardInterrupt:
            print("Scheduler stopped.")


if __name__ == "__main__":
    main()
