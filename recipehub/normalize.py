from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup

from recipehub.config import Settings
from recipehub.models import Ingredient, RecipeRecord
from recipehub.text import clean_text, normalize_text, sha256_text, stable_id


UNIT_ALIASES = {
    "teaspoon": "tsp", "teaspoons": "tsp", "tsp": "tsp", "tsp.": "tsp",
    "tsps": "tsp",
    "tablespoon": "tbsp", "tablespoons": "tbsp", "tbsp": "tbsp", "tbsp.": "tbsp",
    "tbs": "tbsp", "tbsps": "tbsp",
    "cups": "cup", "cup": "cup", "grams": "g", "gram": "g", "g": "g",
    "kilograms": "kg", "kilogram": "kg", "kg": "kg", "milliliters": "ml",
    "milliliter": "ml", "ml": "ml", "liters": "l", "liter": "l", "l": "l",
    "ounces": "oz", "ounce": "oz", "oz": "oz", "pounds": "lb", "pound": "lb", "lbs": "lb", "lb": "lb",
    "clove": "clove", "cloves": "clove", "pinch": "pinch", "pinches": "pinch",
    "handful": "handful", "handfuls": "handful", "slice": "slice", "slices": "slice",
    "piece": "piece", "pieces": "piece", "can": "can", "cans": "can",
}
AMOUNT_RE = re.compile(
    r"^\s*(?P<amount>(?:\d+\s+)?\d+(?:[.,]\d+)?(?:/\d+)?(?:\s*(?:-|to)\s*\d+(?:[.,]\d+)?(?:/\d+)?)?)\s*(?P<rest>.+)$",
    re.IGNORECASE,
)
KNOWN_COUNTRIES = (
    "Vietnamese", "Vietnam", "Thai", "Thailand", "Japanese", "Japan", "Korean", "Korea",
    "Italian", "Italy", "Mexican", "Mexico", "Indian", "India", "Chinese", "China",
    "French", "France", "Canadian", "Canada", "British", "United Kingdom", "Greek", "Greece",
)
INGREDIENT_ALIASES = {
    "chicken breast": "chicken", "chicken thighs": "chicken", "chicken thigh": "chicken",
    "ground beef": "beef", "minced beef": "beef", "beef mince": "beef",
    "spring onions": "green onion", "scallions": "green onion", "spring onion": "green onion",
    "aubergine": "eggplant", "courgette": "zucchini", "capsicum": "bell pepper",
    "coriander leaves": "cilantro", "fresh coriander": "cilantro",
}


def parse_minutes(value: object) -> int | None:
    text = clean_text(str(value or ""))
    if not text:
        return None
    iso = re.fullmatch(r"PT(?:(\d+)H)?(?:(\d+)M)?", text, re.IGNORECASE)
    if iso:
        return int(iso.group(1) or 0) * 60 + int(iso.group(2) or 0)
    hours = re.search(r"(\d+)\s*(?:hours?|hrs?|h)\b", text, re.IGNORECASE)
    minutes = re.search(r"(\d+)\s*(?:minutes?|mins?|m)\b", text, re.IGNORECASE)
    if hours or minutes:
        return int(hours.group(1) if hours else 0) * 60 + int(minutes.group(1) if minutes else 0)
    if text.isdigit():
        return int(text)
    return None


def _ingredient_name(value: str) -> str:
    cleaned = clean_text(value).strip(" ,.;:")
    if "," in cleaned:
        cleaned = cleaned.split(",", 1)[0].strip()
    normalized = normalize_text(cleaned)
    return INGREDIENT_ALIASES.get(normalized, normalized)


def normalize_ingredient(original_text: str, source_name: str = "", amount: str = "") -> Ingredient:
    original_text = clean_text(original_text)
    source_name = clean_text(source_name)
    parsed_amount = clean_text(amount)
    remainder = source_name or original_text
    if not parsed_amount:
        match = AMOUNT_RE.match(remainder)
        if match:
            parsed_amount = match.group("amount").strip()
            remainder = match.group("rest").strip()
    unit = ""
    notes = ""
    if parsed_amount:
        words = remainder.split()
        if words and words[0].lower().rstrip(".,") in UNIT_ALIASES:
            unit = UNIT_ALIASES[words[0].lower().rstrip(".,")]
            remainder = " ".join(words[1:]).strip()
            # Recipe prose commonly says "2 cups of flour". The word "of"
            # belongs to the quantity phrase, not to the ingredient name.
            if remainder.lower().startswith("of "):
                remainder = remainder[3:].strip()
    if "," in remainder:
        remainder, notes = (part.strip() for part in remainder.split(",", 1))
    # Preserve preparation words and source wording; only canonicalize a small known alias set.
    name = _ingredient_name(remainder or source_name or original_text)
    return Ingredient(name=name, original_text=original_text, quantity=parsed_amount, unit=unit, notes=notes)


def _ingredient_list_from_themealdb(payload: dict[str, Any]) -> list[Ingredient]:
    ingredients: list[Ingredient] = []
    for index in range(1, 21):
        name = clean_text(str(payload.get(f"strIngredient{index}") or ""))
        measure = clean_text(str(payload.get(f"strMeasure{index}") or ""))
        if not name:
            continue
        combined = f"{measure} {name}".strip()
        measure_match = AMOUNT_RE.match(measure)
        quantity = measure_match.group("amount").strip() if measure_match else measure
        remainder = measure_match.group("rest").strip() if measure_match else ""
        unit = ""
        if remainder:
            first_word = remainder.split()[0].lower().rstrip(".,")
            unit = UNIT_ALIASES.get(first_word, "")
            if unit:
                remainder = " ".join(remainder.split()[1:]).strip()
        ingredients.append(Ingredient(
            name=_ingredient_name(name),
            original_text=combined,
            quantity=quantity,
            unit=unit,
            notes=remainder,
        ))
    return ingredients


def _split_instructions(value: object) -> list[str]:
    text = clean_text(str(value or ""))
    if not text:
        return []
    raw_steps = re.split(r"\r?\n+|(?<=[.!?])\s+(?=(?:\d+[.)]\s+))", str(value).strip())
    steps = [clean_text(step).strip("-• ") for step in raw_steps]
    steps = [re.sub(r"^\d+[.)]\s*", "", step).strip() for step in steps]
    steps = [step for step in steps if step]
    return steps or [text]


def _infer_country(*values: str) -> str:
    haystack = normalize_text(" ".join(values))
    for country in KNOWN_COUNTRIES:
        if normalize_text(country) in haystack:
            return country
    return ""


def _tag_list(value: object) -> list[str]:
    if isinstance(value, list):
        return [clean_text(str(item)) for item in value if clean_text(str(item))]
    if isinstance(value, str):
        return [clean_text(item) for item in re.split(r"[,;|]", value) if clean_text(item)]
    return []


def _wikibooks_sections(raw_html: str) -> tuple[list[Ingredient], list[str], str]:
    soup = BeautifulSoup(raw_html, "html.parser")
    root = soup.select_one(".mw-parser-output") or soup
    ingredients: list[Ingredient] = []
    instructions: list[str] = []
    description = ""
    for paragraph in root.find_all("p", recursive=False):
        text = clean_text(paragraph.get_text(" ", strip=True))
        if len(text.split()) > 5:
            description = text
            break
    active_section = ""
    active_heading_level = 0
    nodes = root.find_all(["h2", "h3", "h4", "li", "p"])
    for node in nodes:
        if node.name in {"h2", "h3", "h4"}:
            level = int(node.name[1])
            if active_section and level <= active_heading_level:
                active_section = ""
                active_heading_level = 0
            heading_name = clean_text(node.get_text(" ", strip=True)).lower().replace("[edit]", "").strip()
            is_ingredients = "ingredient" in heading_name or "what you need" in heading_name
            is_instructions = any(
                key in heading_name
                for key in ("direction", "method", "instruction", "preparation", "procedure", "steps")
            )
            if is_ingredients:
                active_section = "ingredients"
                active_heading_level = level
            elif is_instructions:
                active_section = "instructions"
                active_heading_level = level
            continue

        if active_section == "ingredients" and node.name == "li":
            item = clean_text(node.get_text(" ", strip=True))
            if item:
                ingredients.append(normalize_ingredient(item))
        elif active_section == "instructions" and node.name in {"li", "p"}:
            # Avoid returning a paragraph twice when it is nested in a list item.
            if node.name == "p" and node.find_parent("li") is not None:
                continue
            item = clean_text(node.get_text(" ", strip=True))
            if item:
                instructions.append(item)
    return ingredients, instructions, description


def normalize_raw_envelope(envelope: dict[str, Any]) -> RecipeRecord:
    source_id = str(envelope["source_id"])
    source_name = str(envelope["source_name"])
    source_record_id = str(envelope["source_record_id"])
    source_url = str(envelope["source_url"])
    payload = envelope["payload"]
    collected_at = str(envelope["collected_at"])
    source_license = str(envelope.get("source_license", "Unknown; check provider terms"))
    source_terms_url = str(envelope.get("source_terms_url", ""))
    attribution = str(envelope.get("attribution", source_name))
    if not isinstance(payload, dict):
        raise ValueError("Raw recipe payload must be a JSON object")

    if source_id == "themealdb":
        title = clean_text(str(payload.get("strMeal") or ""))
        original_title = title
        country = clean_text(str(payload.get("strArea") or ""))
        image_url = clean_text(str(payload.get("strMealThumb") or ""))
        original_recipe_url = clean_text(str(payload.get("strSource") or ""))
        description = ""
        ingredients = _ingredient_list_from_themealdb(payload)
        servings = ""
        prep_minutes = None
        cook_minutes = None
        total_minutes = None
        difficulty = ""
        tools: list[str] = []
        instructions = _split_instructions(payload.get("strInstructions"))
        tips: list[str] = []
        substitutions: list[dict[str, str]] = []
        allergens: list[str] = []  # Only source-declared allergen data is accepted.
        nutrition = None
        categories = _tag_list(payload.get("strCategory")) + _tag_list(payload.get("strTags"))
        language = "en"
        source_updated_at = clean_text(str(payload.get("dateModified") or ""))
        metadata = {
            "youtube_url": clean_text(str(payload.get("strYoutube") or "")),
            "source_category": clean_text(str(payload.get("strCategory") or "")),
        }
    elif source_id == "wikibooks":
        parsed = payload.get("parse", payload)
        if not isinstance(parsed, dict):
            raise ValueError("Wikibooks parse result must be a JSON object")
        page_text = parsed.get("text", "")
        # MediaWiki has returned both legacy {"*": "..."} and plain-string
        # representations for parsed HTML; accept either without losing content.
        raw_html = str(page_text.get("*", "") if isinstance(page_text, dict) else page_text)
        title = clean_text(str(parsed.get("title") or envelope.get("title") or "")).removeprefix("Cookbook:").strip()
        original_title = title
        raw_categories = parsed.get("categories", [])
        categories = [
            clean_text(str(item.get("category", item.get("*", ""))))
            for item in raw_categories if isinstance(item, dict)
        ]
        ingredients, instructions, description = _wikibooks_sections(raw_html)
        country = _infer_country(title, *categories)
        image_url = ""
        original_recipe_url = ""
        servings = ""
        prep_minutes = None
        cook_minutes = None
        total_minutes = None
        difficulty = ""
        tools = []
        tips = []
        substitutions = []
        allergens = []
        nutrition = None
        language = str(envelope.get("language", "en"))
        source_updated_at = clean_text(str(parsed.get("timestamp") or ""))
        metadata = {"page_id": parsed.get("pageid"), "revision_id": parsed.get("revid")}
    else:
        raise ValueError(f"Unsupported source adapter: {source_id}")

    if not title or not ingredients or not instructions:
        raise ValueError("Recipe must contain a title, ingredients, and instructions")

    record_id = stable_id(f"{source_id}:{source_record_id}")
    group_basis = f"{normalize_text(title)}|{normalize_text(country)}"
    duplicate_group_key = hashlib.sha256(group_basis.encode("utf-8")).hexdigest()[:16]
    content = {
        "title": title,
        "country": country,
        "ingredients": [ingredient.__dict__ for ingredient in ingredients],
        "instructions": instructions,
        "servings": servings,
    }
    return RecipeRecord(
        record_id=record_id,
        title=title,
        original_title=original_title,
        country_or_region=country,
        image_url=image_url,
        original_recipe_url=original_recipe_url,
        description=description,
        ingredients=ingredients,
        servings=servings,
        prep_minutes=prep_minutes,
        cook_minutes=cook_minutes,
        total_minutes=total_minutes,
        difficulty=difficulty,
        tools=tools,
        instructions=instructions,
        tips=tips,
        substitutions=substitutions,
        allergens=allergens,
        nutrition=nutrition,
        categories=categories,
        language=language,
        source_name=source_name,
        source_record_id=source_record_id,
        source_url=source_url,
        source_license=source_license,
        source_terms_url=source_terms_url,
        attribution=attribution,
        collected_at=collected_at,
        source_updated_at=source_updated_at,
        processed_at=datetime.now(timezone.utc).isoformat(),
        content_hash=sha256_text(json.dumps(content, sort_keys=True, ensure_ascii=False)),
        duplicate_group_key=duplicate_group_key,
        metadata=metadata,
    )


class NormalizationPipeline:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()

    def run(self) -> dict[str, Any]:
        raw_files = sorted(self.settings.raw_dir.glob("*/runs/*/records/*.json"))
        processed_root = self.settings.processed_dir / "recipes"
        processed_root.mkdir(parents=True, exist_ok=True)
        report: dict[str, Any] = {"raw_records": len(raw_files), "processed": 0, "invalid": []}
        seen: dict[str, list[str]] = defaultdict(list)

        latest: dict[tuple[str, str], tuple[str, Path, dict[str, Any]]] = {}
        for path in raw_files:
            try:
                envelope = json.loads(path.read_text(encoding="utf-8"))
                key = (str(envelope["source_id"]), str(envelope["source_record_id"]))
                collected_at = str(envelope.get("collected_at", ""))
            except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                report["invalid"].append({"file": str(path.relative_to(self.settings.project_root)), "reason": str(exc)})
                continue
            previous = latest.get(key)
            if previous is None or collected_at >= previous[0]:
                latest[key] = (collected_at, path, envelope)

        for _, path, envelope in sorted(latest.values(), key=lambda item: (str(item[2]["source_id"]), str(item[2]["source_record_id"]))):
            try:
                record = normalize_raw_envelope(envelope)
            except (KeyError, TypeError, ValueError) as exc:
                report["invalid"].append({"file": str(path.relative_to(self.settings.project_root)), "reason": str(exc)})
                continue
            source_id = str(envelope["source_id"])
            target = processed_root / source_id / f"{record.record_id}.json"
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(record.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
            report["processed"] += 1
            seen[record.duplicate_group_key].append(record.record_id)

        report["duplicate_candidates"] = [
            {"group_key": key, "record_ids": ids}
            for key, ids in sorted(seen.items()) if len(ids) > 1
        ]
        report_path = self.settings.processed_dir / "quality_report.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report
