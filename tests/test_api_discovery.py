from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from recipehub.api import RecipeService
from recipehub.config import Settings
from recipehub.recipe_crawler import RecipeCrawler


class RecipeDiscoveryTests(unittest.TestCase):
    def test_translation_uses_native_gemini_endpoint_and_caches_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root, raw_dir=root / "raw", processed_dir=root / "processed",
                state_dir=root / "state", llm_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                llm_api_key="unit-test-key", llm_model="gemini-3.8-flash",
            )
            service = RecipeService(settings)
            response = Mock()
            response.json.return_value = {
                "candidates": [{"content": {"parts": [{
                    "text": json.dumps({"translations": ["Bò kho"]}, ensure_ascii=False)
                }]}}]
            }
            with patch("recipehub.api.requests.post", return_value=response) as post:
                self.assertEqual(service._translate_texts(["Beef stew"], "vi"), (["Bò kho"], True))
                self.assertEqual(service._translate_texts(["Beef stew"], "vi"), (["Bò kho"], True))

            self.assertEqual(post.call_count, 1)
            self.assertIn("/models/gemini-3.8-flash:generateContent", post.call_args.args[0])
            self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "unit-test-key")
            self.assertNotIn("unit-test-key", json.dumps(post.call_args.kwargs["json"]))

    def test_chat_uses_native_gemini_endpoint_and_current_reply_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root, raw_dir=root / "raw", processed_dir=root / "processed",
                state_dir=root / "state", llm_api_base_url="https://generativelanguage.googleapis.com/v1beta",
                llm_api_key="unit-test-key", llm_model="gemini-3.8-flash",
            )
            service = RecipeService(settings)
            response = Mock()
            response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Đây là câu trả lời tiếng Việt."}]}}]}
            with patch("recipehub.api.requests.post", return_value=response) as post:
                answer = service._llm_answer("What is in this recipe?", [{"title": "Bun bo"}], "vi")

            self.assertEqual(answer, "Đây là câu trả lời tiếng Việt.")
            self.assertIn("/models/gemini-3.8-flash:generateContent", post.call_args.args[0])
            self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "unit-test-key")
            self.assertIn("Respond in Vietnamese", post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"])

    def test_gemini_search_extracts_grounded_recipe_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(
                project_root=root, raw_dir=root / "raw", processed_dir=root / "processed",
                state_dir=root / "state", llm_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                llm_api_key="unit-test-key",
                llm_model="gemini-3.8-flash",
            )
            service = RecipeService(settings)
            response = Mock()
            response.json.return_value = {
                "candidates": [{"groundingMetadata": {"groundingChunks": [
                    {"web": {"uri": "https://recipes.example.com/bibimbap", "title": "Bibimbap recipe"}},
                    {"web": {"uri": "https://recipes.example.com/bibimbap", "title": "Duplicate"}},
                    {"web": {"uri": "https://food.example.org/bibimbap", "title": "Another recipe"}},
                ]}}]
            }
            with patch("recipehub.api.requests.post", return_value=response) as post:
                pages = service._search_recipe_pages("how to make bibimbap", "en")

            self.assertEqual(len(pages), 2)
            self.assertEqual(pages[0]["url"], "https://recipes.example.com/bibimbap")
            self.assertIn("generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent", post.call_args.args[0])
            self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "unit-test-key")
            self.assertNotIn("unit-test-key", post.call_args.args[0])

    def test_missing_recipe_is_crawled_saved_normalized_and_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            sources_file = root / "sources.json"
            sources_file.write_text("[]", encoding="utf-8")
            settings = Settings(
                project_root=root, sources_file=sources_file, raw_dir=root / "raw",
                processed_dir=root / "processed", state_dir=root / "state",
                delay_seconds=0, llm_api_base_url="https://generativelanguage.googleapis.com/v1beta/openai",
                llm_api_key="unit-test-key", llm_model="gemini-3.8-flash",
            )
            service = RecipeService(settings)
            service._search_recipe_pages = Mock(return_value=[{
                "url": "https://recipes.example.com/bibimbap", "title": "Bibimbap recipe",
            }])
            service._english_search_query = Mock(return_value="bibimbap")
            html = '''<script type="application/ld+json">
            {"@type":"Recipe","name":"Bibimbap","inLanguage":"en",
             "recipeIngredient":["1 cup rice","1 egg"],
             "recipeInstructions":["Cook the rice.","Add the toppings."],
             "publisher":{"@type":"Organization","name":"Example Recipes"}}
            </script>'''
            with patch.object(RecipeCrawler, "_get_html", return_value=html):
                with patch.object(service, "_llm_answer", return_value=None):
                    result = service.chat({"message": "How do I make bibimbap?", "language": "en"})

            self.assertIn("saved 1 recipe page", result["answer"])
            self.assertTrue(result["citations"])
            self.assertEqual(result["citations"][0]["title"], "Bibimbap")
            self.assertEqual(service.knowledge_base.count(), 1)
            self.assertTrue(list((root / "raw").glob("*/runs/*/records/*.json")))
            self.assertTrue(list((root / "processed" / "recipes").glob("*/*.json")))
            manifest = (root / "state" / "crawl_manifest.jsonl").read_text(encoding="utf-8")
            self.assertIn('"discovered_by": "gemini_google_search"', manifest)
            restarted_service = RecipeService(settings)
            self.assertEqual(restarted_service.knowledge_base.count(), 1)


if __name__ == "__main__":
    unittest.main()
