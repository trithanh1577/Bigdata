from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from recipehub.config import Settings
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler


class PipelineTests(unittest.TestCase):
    def test_crawl_to_raw_lake_to_normalized_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources_path = root / "config" / "sources.json"
            sources_path.parent.mkdir(parents=True)
            sources_path.write_text(json.dumps([
                {
                    "id": "themealdb",
                    "name": "TheMealDB",
                    "type": "themealdb",
                    "base_url": "https://meal.test/api/json/v1",
                    "api_key": "1",
                    "areas": ["Italian"],
                    "language": "en",
                    "license": "Test terms",
                    "terms_url": "https://meal.test/terms",
                    "attribution": "TestMealDB",
                },
                {
                    "id": "wikibooks",
                    "name": "Wikibooks Cookbook",
                    "type": "wikibooks",
                    "api_url": "https://wiki.test/w/api.php",
                    "category": "Category:Recipes",
                    "language": "en",
                },
            ]), encoding="utf-8")
            settings = Settings(
                project_root=root,
                sources_file=sources_path,
                raw_dir=root / "data" / "raw",
                processed_dir=root / "data" / "processed",
                state_dir=root / "data" / "state",
                delay_seconds=0,
            )
            crawler = RecipeCrawler(settings)

            def fake_get_json(url: str, params: dict[str, object] | None = None) -> dict[str, object]:
                params = params or {}
                if url.endswith("list.php"):
                    return {"meals": [{"strArea": "Italian"}]}
                if url.endswith("filter.php"):
                    # Deliberately omit strArea as in the real filter response.
                    return {"meals": [{"idMeal": "100", "strMeal": "Tomato pasta"}]}
                if url.endswith("lookup.php"):
                    return {"meals": [{
                        "idMeal": "100",
                        "strMeal": "Tomato pasta",
                        "strArea": "Italian",
                        "strIngredient1": "tomato",
                        "strMeasure1": "2 cups",
                        "strInstructions": "Boil water. Cook the pasta.",
                    }]}
                if params.get("action") == "query":
                    return {"query": {"categorymembers": [{"title": "Cookbook:Simple soup", "pageid": 200}]}}
                if params.get("action") == "parse":
                    return {"parse": {
                        "title": "Cookbook:Simple soup",
                        "pageid": 200,
                        "text": (
                            "<div class='mw-parser-output'><h2>Ingredients</h2>"
                            "<ul><li>1 cup lentils</li></ul><h2>Method</h2>"
                            "<p>Simmer until soft.</p></div>"
                        ),
                    }}
                raise AssertionError(f"Unexpected API request: {url} {params}")

            with patch.object(crawler, "_get_json", side_effect=fake_get_json):
                crawl_report = crawler.crawl(max_items_per_source=1)
            normalize_report = NormalizationPipeline(settings).run()

            self.assertEqual(crawl_report["failed"], 0)
            self.assertEqual(crawl_report["raw_saved"], 2)
            self.assertEqual(normalize_report["processed"], 2)
            self.assertEqual(normalize_report["invalid"], [])
            self.assertEqual(len(list(settings.raw_dir.glob("*/runs/*/records/*.json"))), 2)
            self.assertEqual(len(list((settings.processed_dir / "recipes").glob("*/*.json"))), 2)

            state = json.loads((settings.state_dir / "crawl_cursors.json").read_text(encoding="utf-8"))
            self.assertEqual(state["themealdb"]["areas"]["Italian"], "100")
            self.assertIsNone(state["wikibooks"]["cmcontinue"])

            manifest_lines = (settings.state_dir / "crawl_manifest.jsonl").read_text(encoding="utf-8").splitlines()
            manifest = [json.loads(line) for line in manifest_lines]
            self.assertEqual(len(manifest), 2)
            self.assertEqual({entry["source_id"] for entry in manifest}, {"themealdb", "wikibooks"})
            for entry in manifest:
                self.assertTrue(entry["url"].startswith("https://"))
                self.assertTrue((root / entry["raw_file"]).is_file())


if __name__ == "__main__":
    unittest.main()
