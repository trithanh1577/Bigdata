from recipehub.models import Ingredient, RecipeRecord


def sample_recipe(record_id="test-pasta", title="Tomato Pasta", region="Italian", minutes=25):
    """Synthetic backend test fixture, never used as collected recipe data."""
    return RecipeRecord(
        record_id=record_id, title=title, original_title=title,
        country_or_region=region, image_url="", original_recipe_url="",
        description="Tomato and basil in a classroom test fixture.",
        ingredients=[Ingredient("pasta", "180 g pasta", "180", "g"), Ingredient("tomato", "2 tomatoes", "2")],
        servings="2", prep_minutes=None, cook_minutes=None, total_minutes=minutes,
        difficulty="Easy", tools=[], instructions=["Cook the pasta.", "Stir in tomatoes."],
        tips=[], substitutions=[], allergens=["wheat"], nutrition=None,
        categories=["Main course", "Pasta"], language="en", source_name="Test provider",
        source_record_id=record_id, source_url=f"https://provider.test/recipes/{record_id}",
        source_license="Test fixture", source_terms_url="https://provider.test/terms",
        attribution="Synthetic test source", collected_at="2026-11-09T00:00:00+00:00",
        source_updated_at="", processed_at="2026-11-09T00:01:00+00:00",
        content_hash="test-content-hash", duplicate_group_key="test-duplicate-key",
        metadata={"synthetic": True},
    ).to_dict()
