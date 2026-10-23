from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from recipehub.config import Settings
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
        "countries_or_regions": countries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Global Culinary Knowledge Base — Persons 1 and 2")
    commands = parser.add_subparsers(dest="command", required=True)
    crawl = commands.add_parser("crawl", help="Collect source records into the raw data lake")
    crawl.add_argument("--max-items", type=_positive_int, default=20, help="Maximum recipes per source per run")
    normalize = commands.add_parser("normalize", help="Normalize raw source records into the processed data lake")
    schedule = commands.add_parser("schedule", help="Crawl and normalize on a daily/weekly interval")
    schedule.add_argument("--days", type=_positive_int, default=1, help="Days between runs; default is once per day")
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
    elif args.command == "stats":
        print(json.dumps(_stats(settings), ensure_ascii=False, indent=2))
    elif args.command == "schedule":
        interval_days = args.days
        print(f"Scheduler: crawl + normalize every {interval_days} day(s). Press Ctrl+C to stop.")
        try:
            while True:
                crawl_result = RecipeCrawler(settings).crawl(args.max_items)
                normalize_result = NormalizationPipeline(settings).run()
                print(json.dumps({"crawl": crawl_result, "normalize": normalize_result}, ensure_ascii=False))
                time.sleep(interval_days * 24 * 60 * 60)
        except KeyboardInterrupt:
            print("Scheduler stopped.")


if __name__ == "__main__":
    main()
