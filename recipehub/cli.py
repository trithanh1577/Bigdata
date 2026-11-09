from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from recipehub.config import Settings
from recipehub.knowledge_base import KnowledgeBase
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler


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
        "indexed_records": KnowledgeBase(settings).count(),
        "countries_or_regions": countries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Culinary Knowledge Base")
    commands = parser.add_subparsers(dest="command", required=True)
    crawl = commands.add_parser("crawl", help="Collect source records into the raw data lake")
    crawl.add_argument("--max-items", type=_positive_int, default=20, help="Maximum recipes per source per run")
    normalize = commands.add_parser("normalize", help="Normalize raw source records into the processed data lake")
    commands.add_parser("build", help="Build or refresh the SQLite recipe knowledge base from processed records")
    serve = commands.add_parser("serve", help="Run the Recipe Atlas website and HTTP API")
    serve.add_argument("--host", default="127.0.0.1", help="Bind address; default is local-only")
    serve.add_argument("--port", type=_positive_int, default=8000, help="HTTP port; default is 8000")
    schedule = commands.add_parser("schedule", help="Crawl, normalize, and rebuild on a repeating interval")
    interval = schedule.add_mutually_exclusive_group()
    interval.add_argument("--days", type=_positive_int, help="Days between runs; default is once per day")
    interval.add_argument("--minutes", type=_positive_int, help="Minutes between runs, for example --minutes 30")
    schedule.add_argument("--max-items", type=_positive_int, default=20, help="Maximum recipes per source per run")
    commands.add_parser("stats", help="Show raw/processed counts and country coverage")
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    settings = Settings()
    settings.ensure_directories()

    if args.command == "crawl":
        result = RecipeCrawler(settings).crawl(args.max_items)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["failed"]:
            raise SystemExit(1)
    elif args.command == "normalize":
        result = NormalizationPipeline(settings).run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if result["invalid"]:
            raise SystemExit(1)
    elif args.command == "build":
        result = KnowledgeBase(settings).rebuild()
        print(json.dumps({**result, "database": str(settings.database_file)}, ensure_ascii=False, indent=2))
    elif args.command == "serve":
        if args.port > 65535:
            raise SystemExit("port must be between 1 and 65535")
        from recipehub.api import serve as serve_api
        serve_api(settings, host=args.host, port=args.port)
    elif args.command == "stats":
        print(json.dumps(_stats(settings), ensure_ascii=False, indent=2))
    elif args.command == "schedule":
        interval_seconds = args.minutes * 60 if args.minutes else (args.days or 1) * 24 * 60 * 60
        interval_label = f"{args.minutes} minute(s)" if args.minutes else f"{args.days or 1} day(s)"
        print(f"Scheduler: crawl + normalize + build every {interval_label}, starting now. Press Ctrl+C to stop.")
        try:
            while True:
                run_started = time.monotonic()
                crawl_result = RecipeCrawler(settings).crawl(args.max_items)
                normalize_result = NormalizationPipeline(settings).run()
                build_result = KnowledgeBase(settings).rebuild()
                print(json.dumps({"crawl": crawl_result, "normalize": normalize_result, "knowledge_base": build_result}, ensure_ascii=False))
                remaining = interval_seconds - (time.monotonic() - run_started)
                if remaining > 0:
                    time.sleep(remaining)
        except KeyboardInterrupt:
            print("Scheduler stopped.")


if __name__ == "__main__":
    main()
