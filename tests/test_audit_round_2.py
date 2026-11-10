"""Regression tests for the second tester audit (problems not covered by the ingestion fix on main)."""
from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import urlopen

from recipehub.config import Settings
from recipehub.conversation import ConversationService, plain_text, response_language
from recipehub.gemini import GeminiClient, GeminiUnavailable, RecipeTranslator
from recipehub.knowledge_base import KnowledgeBase
from recipehub.normalize import NormalizationPipeline
from recipehub.recipe_crawler import RecipeCrawler
from recipehub.server import RecipeServer
from tests.helpers import offline_settings, sample_recipe


def gemini_settings(root: Path) -> Settings:
    return Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state",
                    llm_api_base_url="https://generativelanguage.googleapis.com/v1beta", llm_api_key="k", llm_model="gemini-x")


class ChatTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = KnowledgeBase(self.root / "kb.sqlite3")
        self.store.import_records([sample_recipe(minutes=None)])

    def tearDown(self):
        self.temp.cleanup()

    def test_long_messages_do_not_fail_with_400(self):
        service = ConversationService(self.store, offline_settings(self.root))
        service.answer(" ".join(["tomatoes"] * 60))
        service.answer("Find recipes without " + "x" * 150)

    def test_english_dish_words_do_not_switch_reply_to_vietnamese(self):
        self.assertEqual(response_language("How do I bake a bun?", "en"), "en")
        self.assertEqual(response_language("Cách nấu phở", "en"), "vi")

    def test_markdown_is_removed_from_model_text(self):
        self.assertEqual(plain_text("## Bước 1\n**Luộc** mì\n* Thêm muối"), "Bước 1\nLuộc mì\n• Thêm muối")

    def test_general_answer_is_told_about_allergies(self):
        service = ConversationService(self.store, gemini_settings(self.root))
        replies = [json.dumps({"recipe_request": False, "query": ""}), "Ok"]
        with patch.object(service.gemini, "generate", side_effect=replies) as generate:
            service.answer("Gợi ý bữa sáng, tôi dị ứng sữa")
        self.assertIn("sua", generate.call_args.args[0])

    def test_quota_error_still_explains_missing_cooking_times(self):
        service = ConversationService(self.store, gemini_settings(self.root))
        with patch.object(service.gemini, "generate", side_effect=GeminiUnavailable(429)):
            answer = service.answer("Tìm món dưới 30 phút", language="vi")
        self.assertEqual(answer["citations"], [])
        self.assertIn("không ghi thời gian nấu", answer["answer"])
        self.assertIn("429", answer["answer"])


class TranslatorTests(unittest.TestCase):
    def test_gemini_outage_is_not_retried_on_every_request(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = gemini_settings(Path(temp_dir))
            translator = RecipeTranslator(settings, GeminiClient(settings))
            with patch.object(translator.client, "generate", side_effect=GeminiUnavailable(429)) as generate:
                translator.translate(["Beef"], "vi")
                self.assertEqual(translator.translate(["Pork"], "vi"), (["Pork"], False))
            self.assertEqual(generate.call_count, 1)


class IngestionTests(unittest.TestCase):
    def test_invalid_record_is_reported_not_written(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "processed", state_dir=root / "state")
            path = settings.raw_dir / "themealdb" / "runs" / "r1" / "records" / "1.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps({
                # An empty source URL passes normalization but would make the database import fail.
                "source_id": "themealdb", "source_name": "T", "source_record_id": "1", "source_url": "",
                "source_license": "t", "attribution": "t", "collected_at": "2026-11-10T00:00:00+00:00",
                "payload": {"strMeal": "Meal", "strIngredient1": "tomato", "strMeasure1": "1", "strInstructions": "Cook."},
            }), encoding="utf-8")
            report = NormalizationPipeline(settings).run()
            self.assertEqual((report["processed"], len(report["invalid"])), (0, 1))
            KnowledgeBase(root / "kb.sqlite3").import_processed(settings.processed_dir)

    def test_discovered_pages_keep_publisher_url_not_google_redirect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            crawler = RecipeCrawler(Settings(project_root=root, raw_dir=root / "raw", processed_dir=root / "p", state_dir=root / "s", delay_seconds=0))
            html = '<script type="application/ld+json">{"@type":"Recipe","@id":"#recipe","name":"Pho","url":"https://food.example/pho","recipeIngredient":["1 beef"],"recipeInstructions":["Cook."]}</script>'
            with patch.object(crawler, "_get_html", return_value=html) as get_html:
                saved = crawler.collect_discovered_recipe_pages([{"url": "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc", "title": "food.example"}])
            self.assertEqual(saved, 1)
            self.assertEqual(get_html.call_args.kwargs["max_attempts"], 1)
            envelope = json.loads(next(root.glob("raw/*/runs/*/records/*.json")).read_text(encoding="utf-8"))
            self.assertEqual((envelope["source_url"], envelope["source_record_id"]), ("https://food.example/pho",) * 2)
            self.assertTrue(envelope["source_id"].startswith("web_food_example"))


class ServerErrorTests(unittest.TestCase):
    def test_unexpected_errors_return_json_500(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            store = KnowledgeBase(Path(temp_dir) / "kb.sqlite3")
            server = RecipeServer(("127.0.0.1", 0), store, Path(__file__).resolve().parents[1] / "frontend", settings=offline_settings(temp_dir))
            threading.Thread(target=server.serve_forever, daemon=True).start()
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
