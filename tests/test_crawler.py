from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

from recipehub.config import Settings
from recipehub.recipe_crawler import RecipeCrawler


class CrawlerTests(unittest.TestCase):
    def test_themealdb_selection_round_robins_and_advances_area_cursors(self) -> None:
        areas = ["Italian", "Japanese", "Thai", "Vietnamese", "South Korean"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
            )
            crawler = RecipeCrawler(settings)

            def fake_get_json(url: str, params: dict[str, object] | None = None) -> dict[str, object]:
                params = params or {}
                if url.endswith("list.php"):
                    return {"meals": [{"strArea": area} for area in areas]}
                if url.endswith("filter.php"):
                    area = str(params["a"])
                    return {
                        "meals": [
                            # The real filter endpoint may omit strArea.
                            {"idMeal": f"{area}-{index}", "strMeal": f"{area} meal {index}"}
                            for index in range(1, 4)
                        ]
                    }
                if url.endswith("lookup.php"):
                    meal_id = str(params["i"])
                    area, index = meal_id.rsplit("-", 1)
                    return {"meals": [{"idMeal": meal_id, "strMeal": meal_id, "strArea": area}]}
                raise AssertionError(f"Unexpected API URL: {url}")

            source = {
                "id": "themealdb",
                "name": "TheMealDB",
                "type": "themealdb",
                "base_url": "https://www.themealdb.com/api/json/v1",
                "api_key": "1",
                "areas": areas,
            }
            with patch.object(crawler, "_get_json", side_effect=fake_get_json):
                first_records, cursor = crawler._themealdb_records(source, 5)
                second_records, _ = crawler._themealdb_records(source, 5, cursor)

            self.assertEqual([record[0] for record in first_records], [f"{area}-1" for area in areas])
            self.assertEqual([record[0] for record in second_records], [f"{area}-2" for area in areas])
            self.assertEqual(cursor["areas"], {area: f"{area}-1" for area in areas})

    def test_wikibooks_uses_category_continuation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
            )
            crawler = RecipeCrawler(settings)
            listing_calls: list[dict[str, object]] = []

            def fake_get_json(url: str, params: dict[str, object] | None = None) -> dict[str, object]:
                params = params or {}
                if params.get("action") == "query":
                    listing_calls.append(dict(params))
                    if len(listing_calls) == 1:
                        return {
                            "query": {"categorymembers": [{"title": "Cookbook:One", "pageid": 1}]},
                            "continue": {"cmcontinue": "next-page", "continue": "-||"},
                        }
                    return {"query": {"categorymembers": [{"title": "Cookbook:Two", "pageid": 2}]}}
                title = str(params["page"])
                page_id = 1 if title.endswith("One") else 2
                return {"parse": {"title": title, "pageid": page_id, "text": "<p>recipe</p>"}}

            source = {
                "id": "wikibooks",
                "name": "Wikibooks Cookbook",
                "type": "wikibooks",
                "api_url": "https://wiki.test/w/api.php",
                "category": "Category:Recipes",
                "language": "en",
            }
            with patch.object(crawler, "_get_json", side_effect=fake_get_json):
                records, next_cursor = crawler._wikibooks_records(source, 2)

            self.assertEqual([record[0] for record in records], ["1", "2"])
            self.assertEqual(listing_calls[1]["cmcontinue"], "next-page")
            self.assertEqual(listing_calls[0]["cmnamespace"], 102)
            self.assertIsNone(next_cursor["cmcontinue"])

    def test_small_crawls_rotate_starting_area_across_saved_cursors(self) -> None:
        areas = ["Italian", "Japanese", "Thai", "Vietnamese", "Chinese"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            settings = Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state")
            crawler = RecipeCrawler(settings)
            source = {"id": "themealdb", "name": "TheMealDB", "type": "themealdb", "base_url": "https://meal.test/api", "areas": areas}

            def response(url, params=None):
                if url.endswith("list.php"):
                    return {"meals": [{"strArea": area} for area in areas]}
                if url.endswith("filter.php"):
                    return {"meals": [{"idMeal": f"{params['a']}-{index}"} for index in range(3)]}
                if url.endswith("lookup.php"):
                    return {"meals": [{"idMeal": params["i"], "strMeal": params["i"]}]}
                raise AssertionError(url)

            # Old cursor files only contain per-area IDs and must still load.
            cursor = {"areas": {"Italian": "Italian-0"}}
            collected = []
            with patch.object(crawler, "_get_json", side_effect=response):
                for _ in range(3):
                    records, cursor = crawler._themealdb_records(source, 2, cursor)
                    collected.extend(record[0] for record in records)
                    # Simulate a restart through the same on-disk cursor file.
                    crawler._save_state({"themealdb": cursor})
                    cursor = RecipeCrawler(settings)._load_state()["themealdb"]
            self.assertEqual(collected, ["Italian-1", "Japanese-0", "Thai-0", "Vietnamese-0", "Chinese-0", "Italian-2"])

    def test_single_item_crawls_eventually_visit_every_area(self) -> None:
        areas = ["Italian", "Japanese", "Thai"]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            crawler = RecipeCrawler(Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state"))
            source = {"base_url": "https://meal.test/api", "areas": areas}

            def response(url, params=None):
                if url.endswith("list.php"):
                    return {"meals": [{"strArea": area} for area in areas]}
                if url.endswith("filter.php"):
                    return {"meals": [{"idMeal": params["a"]}]}
                return {"meals": [{"idMeal": params["i"]}]}

            cursor = None
            collected = []
            with patch.object(crawler, "_get_json", side_effect=response):
                for _ in areas:
                    records, cursor = crawler._themealdb_records(source, 1, cursor)
                    collected.append(records[0][0])
            self.assertEqual(collected, areas)

    def test_schema_org_adapter_reads_recipe_pages_and_advances_url_cursor(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
                delay_seconds=0,
            )
            crawler = RecipeCrawler(settings)
            source = {
                "id": "sample-site",
                "type": "schema_org_recipe",
                "urls": ["https://recipes.test/one", "https://recipes.test/two"],
                "language": "en",
            }
            html = '<script type="application/ld+json">{"@type":"Recipe","name":"Test recipe"}</script>'
            with patch.object(crawler, "_get_html", return_value=html) as fetch:
                records, cursor = crawler._schema_org_records(source, 1)
                next_records, next_cursor = crawler._schema_org_records(source, 1, cursor)

            self.assertEqual(fetch.call_args_list[0].args[0], "https://recipes.test/one")
            self.assertEqual(fetch.call_args_list[1].args[0], "https://recipes.test/two")
            self.assertEqual(records[0][2]["html"], html)
            self.assertEqual(records[0][2]["json_ld"]["name"], "Test recipe")
            self.assertEqual(cursor["next_index"], 1)
            self.assertEqual(next_records[0][1], "https://recipes.test/two")
            self.assertEqual(next_cursor["next_index"], 0)

    def test_wikibooks_rejects_placeholder_contact_in_user_agent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
                user_agent="RecipeBot/1.0 (contact: your-email@example.org)",
            )
            crawler = RecipeCrawler(settings)
            source = {
                "id": "wikibooks",
                "name": "Wikibooks Cookbook",
                "type": "wikibooks",
                "api_url": "https://en.wikibooks.org/w/api.php",
            }

            with self.assertRaisesRegex(ValueError, "real contact email or project URL"):
                crawler._wikibooks_records(source, 1)

    def test_malformed_source_response_is_reported_as_a_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
            )
            crawler = RecipeCrawler(settings)
            source = {
                "id": "themealdb",
                "name": "TheMealDB",
                "type": "themealdb",
                "base_url": "https://meal.test/api/json/v1",
                "api_key": "1",
                "areas": ["Italian"],
            }
            with patch.object(crawler, "_get_json", return_value={"meals": "not-a-list"}):
                with self.assertRaisesRegex(ValueError, "list of JSON objects"):
                    crawler._themealdb_records(source, 1)

    def test_retries_transient_server_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root,
                sources_file=root / "sources.json",
                raw_dir=root / "raw",
                processed_dir=root / "processed",
                state_dir=root / "state",
                delay_seconds=0,
            )
            crawler = RecipeCrawler(settings)
            unavailable = Mock(status_code=503, headers={})
            success = Mock(status_code=200, headers={})
            success.json.return_value = {"ok": True}
            with patch.object(crawler.session, "get", side_effect=[unavailable, success]) as get:
                with patch("recipehub.recipe_crawler.time.sleep"):
                    self.assertEqual(crawler._get_json("https://api.test/recipes"), {"ok": True})
            self.assertEqual(get.call_count, 2)

    def test_api_errors_are_reported_instead_of_silent_empty_results(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crawler = RecipeCrawler(Settings(raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state", delay_seconds=0))
            response = Mock(status_code=200, headers={})
            response.json.return_value = {"error": {"code": "badcontinue", "info": "Invalid cursor"}}
            with patch.object(crawler.session, "get", return_value=response), self.assertRaisesRegex(ValueError, "Provider API error"):
                crawler._get_json("https://wiki.test/api.php")


if __name__ == "__main__":
    unittest.main()
