from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from recipehub.config import Settings
from recipehub.conversation import ConversationService
from recipehub.gemini import GeminiClient, RecipeTranslator
from recipehub.knowledge_base import KnowledgeBase
from recipehub.recipe_crawler import RecipeCrawler
from tests.helpers import sample_recipe


def gemini_settings(root: Path, base_url: str = "https://generativelanguage.googleapis.com/v1beta") -> Settings:
    sources_file = root / "sources.json"
    sources_file.write_text("[]", encoding="utf-8")
    return Settings(
        project_root=root, sources_file=sources_file, raw_dir=root / "raw", processed_dir=root / "processed",
        state_dir=root / "state", delay_seconds=0, llm_api_base_url=base_url,
        llm_api_key="unit-test-key", llm_model="gemini-3.8-flash",
    )


def gemini_reply(text: str) -> Mock:
    response = Mock()
    response.json.return_value = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
    return response


class RecipeDiscoveryTests(unittest.TestCase):
    def test_invalid_translation_structure_falls_back_without_poisoning_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            settings = gemini_settings(Path(temp_dir))
            translator = RecipeTranslator(settings, GeminiClient(settings))
            for response in ("[]", "null", "42", '"text"', '{}', '{"translations":[""]}', '{"translations":[1]}'):
                with self.subTest(response=response), patch.object(translator.client, "generate", return_value=response):
                    self.assertEqual(translator.translate(["Beef stew"], "vi"), (["Beef stew"], False))
            with patch.object(translator.client, "generate", return_value='{"translations":["Bò kho"]}'):
                self.assertEqual(translator.translate(["Beef stew"], "vi"), (["Bò kho"], True))

    def test_greeting_with_existing_collection_uses_chat_instead_of_recipe_citations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ConversationService(KnowledgeBase(root / "kb.sqlite3"), gemini_settings(root))
            service.store.import_records([sample_recipe()])
            replies = [json.dumps({"recipe_request": False, "query": ""}), "I'm here to help in the kitchen!"]
            with patch.object(service.gemini, "generate", side_effect=replies) as generate, \
                 patch.object(service.gemini, "search_recipe_pages") as search:
                result = service.answer("How are you?")
            self.assertEqual(result["answer"], "I'm here to help in the kitchen!")
            self.assertEqual(result["citations"], [])
            self.assertEqual(generate.call_count, 2)
            search.assert_not_called()

    def test_translation_uses_native_gemini_endpoint_and_caches_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            # The legacy OpenAI-compatible base URL must still reach the native endpoint.
            settings = gemini_settings(Path(temp_dir), "https://generativelanguage.googleapis.com/v1beta/openai")
            translator = RecipeTranslator(settings, GeminiClient(settings))
            reply = gemini_reply(json.dumps({"translations": ["Bò kho"]}, ensure_ascii=False))
            with patch("recipehub.gemini.requests.post", return_value=reply) as post:
                self.assertEqual(translator.translate(["Beef stew"], "vi"), (["Bò kho"], True))
                self.assertEqual(translator.translate(["Beef stew"], "vi"), (["Bò kho"], True))

            self.assertEqual(post.call_count, 1)
            self.assertEqual(post.call_args.args[0], "https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent")
            self.assertEqual(post.call_args.kwargs["headers"]["x-goog-api-key"], "unit-test-key")
            self.assertNotIn("unit-test-key", json.dumps(post.call_args.kwargs["json"]))

    def test_grounded_answer_uses_reply_language(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ConversationService(KnowledgeBase(root / "kb.sqlite3"), gemini_settings(root))
            with patch("recipehub.gemini.requests.post", return_value=gemini_reply("Đây là câu trả lời tiếng Việt.")) as post:
                answer = service._grounded_answer("What is in this recipe?", {}, [{"title": "Bun bo"}], "vi")

            self.assertEqual(answer, "Đây là câu trả lời tiếng Việt.")
            self.assertIn("Answer in Vietnamese", post.call_args.kwargs["json"]["systemInstruction"]["parts"][0]["text"])

    def test_gemini_search_extracts_grounded_recipe_urls(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            client = GeminiClient(gemini_settings(Path(temp_dir)))
            response = Mock()
            response.json.return_value = {
                "candidates": [{"groundingMetadata": {"groundingChunks": [
                    {"web": {"uri": "https://recipes.example.com/bibimbap", "title": "Bibimbap recipe"}},
                    {"web": {"uri": "https://recipes.example.com/bibimbap", "title": "Duplicate"}},
                    {"web": {"uri": "https://food.example.org/bibimbap", "title": "Another recipe"}},
                ]}}]
            }
            with patch("recipehub.gemini.requests.post", return_value=response) as post:
                pages = client.search_recipe_pages("how to make bibimbap", "en")

            self.assertEqual([page["url"] for page in pages], ["https://recipes.example.com/bibimbap", "https://food.example.org/bibimbap"])
            self.assertEqual(post.call_args.kwargs["json"]["tools"], [{"google_search": {}}])
            self.assertNotIn("unit-test-key", post.call_args.args[0])

    def test_missing_recipe_is_searched_saved_normalized_and_indexed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = gemini_settings(root)
            store = KnowledgeBase(root / "kb.sqlite3")
            service = ConversationService(store, settings)
            html = '''<script type="application/ld+json">
            {"@type":"Recipe","name":"Bibimbap","inLanguage":"en",
             "recipeIngredient":["1 cup rice","1 egg"],
             "recipeInstructions":["Cook the rice.","Add the toppings."]}
            </script>'''
            replies = [json.dumps({"recipe_request": True, "query": "bibimbap"}), "Bibimbap: cook the rice, add the toppings."]
            with patch.object(service.gemini, "generate", side_effect=replies), \
                 patch.object(service.gemini, "search_recipe_pages", return_value=[{"url": "https://recipes.example.com/bibimbap", "title": "Bibimbap"}]) as search, \
                 patch.object(RecipeCrawler, "_get_html", return_value=html):
                result = service.answer("Cách làm cơm trộn Hàn Quốc?", language="vi")

            search.assert_called_once()
            self.assertEqual(search.call_args.args[0], "bibimbap")
            self.assertEqual(result["language"], "vi")
            self.assertEqual([item["title"] for item in result["citations"]], ["Bibimbap"])
            self.assertEqual(store.stats()["recipes"], 1)
            self.assertTrue(list((root / "raw").glob("*/runs/*/records/*.json")))
            manifest = (root / "state" / "crawl_manifest.jsonl").read_text(encoding="utf-8")
            self.assertIn('"discovered_by": "gemini_google_search"', manifest)

    def test_small_talk_is_answered_like_a_normal_chat_with_server_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service = ConversationService(KnowledgeBase(root / "kb.sqlite3"), gemini_settings(root))
            not_recipe = json.dumps({"recipe_request": False, "query": ""})
            replies = [not_recipe, "Chào bạn! Hôm nay bạn muốn nấu gì?", not_recipe, "Bạn tên Nam."]
            with patch.object(service.gemini, "generate", side_effect=replies) as generate, \
                 patch.object(service.gemini, "search_recipe_pages") as search:
                first = service.answer("Xin chào, mình tên Nam")
                second = service.answer("Mình tên gì?", session_id=first["session_id"])

            self.assertEqual(first["answer"], "Chào bạn! Hôm nay bạn muốn nấu gì?")
            self.assertEqual(second["answer"], "Bạn tên Nam.")
            self.assertEqual(second["citations"], [])
            search.assert_not_called()
            self.assertEqual(
                [turn["text"] for turn in generate.call_args.kwargs["history"]],
                ["Xin chào, mình tên Nam", "Chào bạn! Hôm nay bạn muốn nấu gì?"],
            )


if __name__ == "__main__":
    unittest.main()
