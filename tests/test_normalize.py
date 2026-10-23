from __future__ import annotations

import unittest

from recipehub.normalize import normalize_raw_envelope


def envelope(source_id: str, payload: dict[str, object]) -> dict[str, object]:
    return {
        "source_id": source_id,
        "source_name": "TheMealDB" if source_id == "themealdb" else "Wikibooks Cookbook",
        "source_record_id": "test-1",
        "source_url": "https://example.test/recipe",
        "source_license": "test license",
        "source_terms_url": "https://example.test/terms",
        "attribution": "Test source",
        "language": "en",
        "collected_at": "2026-10-23T00:00:00+00:00",
        "payload": payload,
    }


class NormalizeTests(unittest.TestCase):
    def test_themealdb_quantity_and_provenance(self) -> None:
        record = normalize_raw_envelope(envelope("themealdb", {
            "strMeal": "Demo soup",
            "strArea": "Vietnamese",
            "strIngredient1": "Chicken",
            "strMeasure1": "400 g",
            "strInstructions": "Boil the soup.",
        }))

        self.assertEqual(record.title, "Demo soup")
        self.assertEqual(record.country_or_region, "Vietnamese")
        self.assertEqual(record.ingredients[0].quantity, "400")
        self.assertEqual(record.ingredients[0].unit, "g")
        self.assertEqual(record.source_url, "https://example.test/recipe")
        self.assertEqual(record.allergens, [])
        self.assertIsNone(record.nutrition)

    def test_rejects_non_object_raw_payload_with_clear_error(self) -> None:
        raw = envelope("themealdb", {})
        raw["payload"] = []
        with self.assertRaisesRegex(ValueError, "payload must be a JSON object"):
            normalize_raw_envelope(raw)

    def test_wikibooks_parses_amounts_nested_headings_and_paragraph_steps(self) -> None:
        html = (
            "<div class='mw-parser-output'><h2>Ingredients</h2>"
            "<ul><li>2 cups of tomato</li></ul><h3>For the filling</h3>"
            "<ul><li>1 cup of cheese</li></ul><h2>Method</h2>"
            "<p>Mix everything.</p><h3>Finish</h3><p>Bake until ready.</p></div>"
        )
        for text in (html, {"*": html}):
            with self.subTest(text_type=type(text).__name__):
                record = normalize_raw_envelope(envelope("wikibooks", {
                    "parse": {"title": "Cookbook:Demo soup", "text": text, "categories": []}
                }))
                self.assertEqual([ingredient.name for ingredient in record.ingredients], ["tomato", "cheese"])
                self.assertEqual(record.ingredients[0].quantity, "2")
                self.assertEqual(record.ingredients[0].unit, "cup")
                self.assertEqual(record.ingredients[1].quantity, "1")
                self.assertEqual(record.instructions, ["Mix everything.", "Bake until ready."])


if __name__ == "__main__":
    unittest.main()
