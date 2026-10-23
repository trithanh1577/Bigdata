from __future__ import annotations

from dataclasses import asdict, dataclass, field
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
