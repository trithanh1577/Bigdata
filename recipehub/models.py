from __future__ import annotations

from dataclasses import asdict, dataclass, field
import math
from typing import Any


SCHEMA_VERSION = 1


@dataclass
class Ingredient:
    """Normalized ingredient while preserving its wording from the source."""

    name: str
    original_text: str
    quantity: str = ""
    unit: str = ""
    notes: str = ""


@dataclass
class RecipeRecord:
    """Common processed format for recipes from different providers."""

    record_id: str
    title: str
    original_title: str
    country_or_region: str
    image_url: str
    original_recipe_url: str
    description: str
    ingredients: list[Ingredient]
    servings: str
    prep_minutes: int | None
    cook_minutes: int | None
    total_minutes: int | None
    difficulty: str
    tools: list[str]
    instructions: list[str]
    tips: list[str]
    substitutions: list[dict[str, str]]
    allergens: list[str]
    nutrition: dict[str, Any] | None
    categories: list[str]
    language: str
    source_name: str
    source_record_id: str
    source_url: str
    source_license: str
    source_terms_url: str
    attribution: str
    collected_at: str
    source_updated_at: str
    processed_at: str
    content_hash: str
    duplicate_group_key: str
    metadata: dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def recipe_record_from_dict(value: dict[str, Any]) -> RecipeRecord:
    """Rehydrate a record written by the normalizer."""
    data = dict(value)
    data["ingredients"] = [Ingredient(**ingredient) for ingredient in data.get("ingredients", [])]
    allowed = RecipeRecord.__dataclass_fields__
    return RecipeRecord(**{key: item for key, item in data.items() if key in allowed})


def validate_recipe(value: dict[str, Any]) -> dict[str, Any]:
    """Validate the shared schema at the database boundary, preserving provenance."""
    if not isinstance(value, dict) or type(value.get("schema_version")) is not int or value["schema_version"] != SCHEMA_VERSION:
        raise ValueError("Expected a schema_version 1 recipe object")
    for name in ("record_id", "title", "source_name", "source_record_id", "source_url", "source_license", "attribution", "collected_at"):
        if not isinstance(value.get(name), str) or not value[name].strip():
            raise ValueError(f"Recipe field '{name}' must be a nonempty string")
    for name in ("ingredients", "instructions", "categories", "allergens", "tools", "tips", "substitutions"):
        if not isinstance(value.get(name), list):
            raise ValueError(f"Recipe field '{name}' must be an array")
    if not value["ingredients"] or not value["instructions"]:
        raise ValueError("A recipe needs ingredients and instructions")
    for ingredient in value["ingredients"]:
        if not isinstance(ingredient, dict) or not isinstance(ingredient.get("name"), str) or not ingredient["name"].strip() or not isinstance(ingredient.get("original_text"), str):
            raise ValueError("Each ingredient needs a name and original_text")
        if any(not isinstance(ingredient.get(key, ""), str) for key in ("quantity", "unit", "notes")):
            raise ValueError("Ingredient quantity, unit, and notes must be strings")
    for name in ("instructions", "categories", "allergens", "tools", "tips"):
        if any(not isinstance(item, str) or not item.strip() for item in value[name]):
            raise ValueError(f"Recipe field '{name}' must contain nonempty strings")
    for name in ("prep_minutes", "cook_minutes", "total_minutes"):
        number = value.get(name)
        if number is not None and (type(number) is not int or number < 0 or not math.isfinite(number)):
            raise ValueError(f"Recipe field '{name}' must be a nonnegative integer or null")
    if value.get("nutrition") is not None and not isinstance(value["nutrition"], dict):
        raise ValueError("Recipe nutrition must be an object or null")
    if any(not isinstance(item, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in item.items()) for item in value["substitutions"]):
        raise ValueError("Substitutions must contain source-declared string fields")
    try:
        record = recipe_record_from_dict(value)
    except TypeError as exc:
        raise ValueError(f"Recipe does not match the shared schema: {exc}") from exc
    data = record.to_dict()
    for name, item in data.items():
        if name not in {"schema_version", "ingredients", "instructions", "categories", "allergens", "tools", "tips", "substitutions", "prep_minutes", "cook_minutes", "total_minutes", "nutrition", "metadata"} and not isinstance(item, str):
            raise ValueError(f"Recipe field '{name}' must be a string")
    if not isinstance(data["metadata"], dict):
        raise ValueError("Recipe metadata must be an object")
    return data
