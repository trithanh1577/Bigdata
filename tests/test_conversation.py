import json
import tempfile
import time
import unittest
from pathlib import Path

from recipehub.conversation import ConversationService, SessionNotFound, SESSION_TTL_SECONDS
from recipehub.knowledge_base import KnowledgeBase
from tests.helpers import offline_settings, sample_recipe


class ConversationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = KnowledgeBase(Path(self.temp.name) / "recipes.sqlite3")
        self.first = sample_recipe()
        second = sample_recipe("test-rice", "Ginger Rice", "Japanese", 15)
        second.update(ingredients=[{"name": "rice", "original_text": "1 cup rice"}], allergens=[], categories=["Rice"])
        self.store.import_records([self.first, second])
        self.service = ConversationService(self.store, offline_settings(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_discovery_and_followups_quote_source_records(self):
        response = self.service.answer("Find recipes from Italy")
        self.assertEqual(response["citations"][0]["record_id"], "test-pasta")
        session = response["session_id"]
        for question, expected in (("What are its ingredients?", "180 g pasta"), ("How do I cook it?", "1. Cook the pasta."), ("Where does it come from?", self.first["source_url"]), ("How long does it take?", "25 minutes")):
            with self.subTest(question=question):
                answer = self.service.answer(question, session_id=session)
                self.assertIn(expected, answer["answer"])
                self.assertEqual(answer["citations"][0]["record_id"], "test-pasta")

    def test_context_never_bypasses_changed_exclusions(self):
        first = self.service.answer("Find Italian recipes")
        answer = self.service.answer("What are its ingredients?", {"exclude_ingredients": ["wheat"]}, first["session_id"])
        self.assertEqual(answer["citations"], [])
        self.assertNotIn("180 g pasta", answer["answer"])

    def test_missing_data_is_not_invented_and_allergens_do_not_imply_safety(self):
        first = self.service.answer("Find Italian recipes")
        for question, text in (("What is its nutrition?", "does not supply structured nutrition"), ("What substitutions does it have?", "does not supply substitutions"), ("Is it safe for my allergy?", "cannot certify")):
            answer = self.service.answer(question, session_id=first["session_id"])
            self.assertIn(text, answer["answer"])
            self.assertEqual(answer["citations"][0]["record_id"], "test-pasta")

    def test_supplied_nutrition_and_substitutions_are_rendered_verbatim(self):
        record = {**self.first, "nutrition": {"energy": "source example"}, "substitutions": [{"ingredient": "tomato", "replacement": "source-declared example"}]}
        self.store.import_records([record])
        first = self.service.answer("Find Italian recipes")
        self.assertIn("source example", self.service.answer("What is its nutrition?", session_id=first["session_id"])["answer"])
        self.assertIn("source-declared example", self.service.answer("What substitutions does it have?", session_id=first["session_id"])["answer"])

    def test_natural_language_exclusions_persist_only_in_their_session(self):
        first = self.service.answer("Find recipes without wheat")
        self.assertTrue(first["citations"])
        self.assertTrue(all(item["record_id"] == "test-rice" for item in first["citations"]))
        second = self.service.answer("Find Italian recipes", session_id=first["session_id"])
        self.assertEqual(second["citations"], [])
        fresh = self.service.answer("Find Italian recipes")
        self.assertNotEqual(first["session_id"], fresh["session_id"])
        self.assertTrue(fresh["citations"])

    def test_time_limits_and_unrelated_queries(self):
        answer = self.service.answer("Find recipes under 20 minutes")
        self.assertEqual([item["record_id"] for item in answer["citations"]], ["test-rice"])
        self.assertEqual(self.service.answer("Tell me about astronomy")["citations"], [])
        self.assertEqual(self.service.answer("What are its ingredients?")["citations"], [])

    def test_vietnamese_answers_without_gemini_stay_vietnamese(self):
        first = self.service.answer("Tìm món Italian")
        self.assertEqual(first["language"], "vi")
        self.assertIn("Đây là các công thức", first["answer"])
        detail = self.service.answer("Nguyên liệu của nó là gì?", session_id=first["session_id"])
        self.assertIn("180 g pasta", detail["answer"])
        self.assertIn("Mở bản ghi", detail["answer"])
        self.assertIn("món nào", self.service.answer("Nguyên liệu của nó là gì?")["answer"])

    def test_vietnamese_suggestion_chips_work_without_gemini(self):
        for question, expected in (("Tìm món có cà chua", "test-pasta"), ("Tìm món ăn Nhật Bản", "test-rice"), ("Tìm món dưới 20 phút", "test-rice"), ("Tìm món Ý", "test-pasta")):
            with self.subTest(question=question):
                # Both fixtures share a "Tomato ..." description, so check membership.
                self.assertIn(expected, [item["record_id"] for item in self.service.answer(question)["citations"]])
    def test_session_expiration_and_validation(self):
        first = self.service.answer("Find recipes")
        with self.store.connect() as db:
            db.execute("UPDATE chat_sessions SET updated_at=?", (time.time() - SESSION_TTL_SECONDS - 10,))
        with self.assertRaises(SessionNotFound):
            self.service.answer("What are its ingredients?", session_id=first["session_id"])
        for message, session in (("", None), ("x" * 1001, None), ("Find recipes", "made-up")):
            with self.assertRaises(ValueError):
                self.service.answer(message, session_id=session)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM chat_sessions").fetchone()[0], 0)
