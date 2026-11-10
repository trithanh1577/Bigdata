"""Regression tests for the second tester audit: one test per reported or found problem."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import threading
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from recipehub.config import Settings
from recipehub.conversation import ConversationService, plain_text, response_language
from recipehub.gemini import GeminiClient, GeminiUnavailable, RecipeTranslator
from recipehub.knowledge_base import INDEX_VERSION, KnowledgeBase, fold
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler
from recipehub.server import RecipeServer
from tests.helpers import offline_settings, sample_recipe


def ingredient(name: str) -> dict[str, str]:
    return {"name": name, "original_text": f"1 {name}", "quantity": "1", "unit": "", "notes": ""}


class ChatAndSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = KnowledgeBase(Path(self.temp.name) / "kb.sqlite3")
        self.pasta = sample_recipe()
        self.pasta["ingredients"].append(ingredient("milk"))
        self.rice = sample_recipe("test-rice", "Ginger Rice", "Japanese", 15)
        self.rice.update(ingredients=[ingredient("rice"), ingredient("peanut")], allergens=[], categories=["Rice"], description="Rice bowl", difficulty="Easy")
        self.store.import_records([self.pasta, self.rice])
        self.service = ConversationService(self.store, offline_settings(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def ids(self, answer):
        return [item["record_id"] for item in answer["citations"]]

    def test_1_vietnamese_allergy_excludes_english_ingredient(self):
        self.assertEqual(self.ids(self.service.answer("Tìm món Italian, tôi dị ứng sữa")), [])
        # "đậu phộng" has "đ", which accent folding used to keep.
        self.assertNotIn("test-rice", self.ids(self.service.answer("Tìm món, tôi dị ứng đậu phộng")))
        self.assertEqual(self.store.search({"exclude_ingredients": ["sữa"]})["total"], 1)

    def test_3_named_dish_wins_over_pronoun_context(self):
        first = self.service.answer("Find Italian recipes")
        answer = self.service.answer("How do I cook Ginger Rice? Is it easy?", session_id=first["session_id"])
        self.assertEqual(self.ids(answer), ["test-rice"])

    def test_4_small_talk_does_not_list_recipes(self):
        small_talk = self.service.answer("How are you?")
        self.assertEqual(self.ids(small_talk), [])
        self.assertIn("kitchen assistant", small_talk["answer"])
        self.assertTrue(self.ids(self.service.answer("Find recipes")))

    def test_5_search_box_understands_vietnamese_ingredients(self):
        self.assertEqual([item["record_id"] for item in self.store.search({"q": "cà chua"})["items"]], ["test-pasta"])
        self.assertEqual(self.store.search({"q": "tomato"})["total"], 1)

    def test_dj_letter_is_folded_for_search_and_titles(self):
        self.assertEqual(fold("Đậu phộng"), "dau phong")
        record = sample_recipe("test-vi", "Bánh đậu xanh", "Vietnamese", 30)
        self.store.import_records([record])
        self.assertEqual(self.store.search({"q": "banh dau"})["items"][0]["record_id"], "test-vi")
        self.assertEqual(self.store.search({"q": "đậu"})["items"][0]["record_id"], "test-vi")

    def test_long_messages_do_not_fail_with_400(self):
        self.service.answer(" ".join(["tomatoes"] * 60))
        self.service.answer("Find recipes without " + "x" * 150)

    def test_english_dish_words_do_not_switch_reply_to_vietnamese(self):
        self.assertEqual(response_language("How do I bake a bun?", "en"), "en")
        self.assertEqual(response_language("Cách nấu phở", "en"), "vi")

    def test_markdown_is_removed_from_model_text(self):
        self.assertEqual(plain_text("## Bước 1\n**Luộc** mì\n* Thêm muối"), "Bước 1\nLuộc mì\n• Thêm muối")

    def test_general_answer_is_told_about_allergies(self):
        settings = Settings(project_root=Path(self.temp.name), state_dir=Path(self.temp.name) / "s",
                            llm_api_base_url="https://generativelanguage.googleapis.com/v1beta", llm_api_key="k", llm_model="gemini-x")
        service = ConversationService(self.store, settings)
        replies = [json.dumps({"recipe_request": False, "query": ""}), "Ok"]
        with patch.object(service.gemini, "generate", side_effect=replies) as generate:
            service.answer("Gợi ý bữa sáng, tôi dị ứng sữa")
        self.assertIn("milk", generate.call_args.args[0])


class OldDatabaseTests(unittest.TestCase):
    def test_existing_database_is_reindexed_after_fold_change(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "kb.sqlite3"
            store = KnowledgeBase(path)
            store.import_records([sample_recipe()])
            with closing(sqlite3.connect(path)) as db:
                db.execute("PRAGMA user_version=0")
            store = KnowledgeBase(path)
            self.assertEqual(store.import_records([sample_recipe()])["updated"], 1)
            with closing(sqlite3.connect(path)) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], INDEX_VERSION)


class TranslatorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        settings = Settings(project_root=Path(self.temp.name), state_dir=Path(self.temp.name) / "s",
                            llm_api_base_url="https://generativelanguage.googleapis.com/v1beta", llm_api_key="k", llm_model="gemini-x")
        self.translator = RecipeTranslator(settings, GeminiClient(settings))

    def tearDown(self):
        self.temp.cleanup()

    def test_6_wrong_json_shape_falls_back_to_source_text(self):
        with patch.object(self.translator.client, "generate", return_value="[]"):
            self.assertEqual(self.translator.translate(["Beef"], "vi"), (["Beef"], False))

    def test_gemini_outage_is_not_retried_on_every_request(self):
        with patch.object(self.translator.client, "generate", side_effect=GeminiUnavailable(429)) as generate:
            self.translator.translate(["Beef"], "vi")
            self.assertEqual(self.translator.translate(["Pork"], "vi"), (["Pork"], False))
        self.assertEqual(generate.call_count, 1)


class PipelineTests(unittest.TestCase):
    def test_2_parallel_normalization_runs_do_not_collide(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state")
            for index in range(5):
                path = settings.raw_dir / "themealdb" / "runs" / "r1" / "records" / f"{index}.json"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({
                    "source_id": "themealdb", "source_name": "T", "source_record_id": str(index), "source_url": f"https://t.test/{index}",
                    "source_license": "t", "attribution": "t", "collected_at": "2026-11-10T00:00:00+00:00",
                    "payload": {"strMeal": f"Meal {index}", "strIngredient1": "tomato", "strMeasure1": "1", "strInstructions": "Cook."},
                }), encoding="utf-8")
            errors = []

            def run():
                try:
                    NormalizationPipeline(settings).run()
                except Exception as exc:  # noqa: BLE001 - any failure is the bug
                    errors.append(exc)

            threads = [threading.Thread(target=run) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
            self.assertEqual(errors, [])
            self.assertEqual(list(settings.processed_dir.rglob("*.tmp")), [])
            self.assertEqual(KnowledgeBase(root / "kb.sqlite3").import_processed(settings.processed_dir)["files"], 5)

    def test_7_small_crawls_rotate_through_all_areas(self):
        areas = ["Italian", "Japanese", "Thai"]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crawler = RecipeCrawler(Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "p", state_dir=root / "s"))

            def fake_get_json(url, params=None):
                if url.endswith("list.php"):
                    return {"meals": [{"strArea": area} for area in areas]}
                if url.endswith("filter.php"):
                    return {"meals": [{"idMeal": f"{params['a']}-{i}"} for i in range(1, 4)]}
                return {"meals": [{"idMeal": params["i"]}]}

            source = {"id": "themealdb", "type": "themealdb", "base_url": "https://m.test", "areas": areas}
            picked, cursor = [], None
            with patch.object(crawler, "_get_json", side_effect=fake_get_json):
                for _ in range(3):
                    records, cursor = crawler._themealdb_records(source, 2, cursor)
                    picked += [record[0].split("-")[0] for record in records]
            self.assertEqual(set(picked), set(areas))

    def test_discovered_pages_keep_publisher_url_not_google_redirect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crawler = RecipeCrawler(Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "p", state_dir=root / "s", delay_seconds=0))
            html = '<script type="application/ld+json">{"@type":"Recipe","@id":"#recipe","name":"Pho","url":"https://food.example/pho","recipeIngredient":["1 beef"],"recipeInstructions":["Cook."]}</script>'
            with patch.object(crawler, "_get_html", return_value=html) as get_html:
                self.assertEqual(crawler.collect_discovered_recipe_pages([{"url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "title": "food.example"}]), 1)
            self.assertEqual(get_html.call_args.kwargs["max_attempts"], 1)
            envelope = json.loads(next(root.glob("raw/*/runs/*/records/*.json")).read_text(encoding="utf-8"))
            self.assertEqual(envelope["source_url"], "https://food.example/pho")
            self.assertEqual(envelope["source_record_id"], "https://food.example/pho")
            self.assertTrue(envelope["source_id"].startswith("web_food_example"))


class ServerErrorTests(unittest.TestCase):
    def test_unexpected_errors_return_json_500(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = KnowledgeBase(Path(temp_dir) / "kb.sqlite3")
            server = RecipeServer(("127.0.0.1", 0), store, Path(__file__).resolve().parents[1] / "frontend", settings=offline_settings(temp_dir))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                with patch.object(store, "stats", side_effect=RuntimeError("boom")), self.assertRaises(HTTPError) as caught:
                    urlopen(f"http://127.0.0.1:{server.server_port}/api/v1/health", timeout=5)
                self.assertEqual(caught.exception.code, 500)
                self.assertEqual(json.loads(caught.exception.read())["error"]["status"], 500)
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
