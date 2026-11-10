import copy
import json
import tempfile
import unittest
from pathlib import Path

from recipehub.knowledge_base import KnowledgeBase, parse_filters
from recipehub.text import normalize_recipe_query
from tests.helpers import sample_recipe


class KnowledgeBaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.store = KnowledgeBase(self.root / "recipes.sqlite3")
        self.pasta = sample_recipe()
        self.soup = sample_recipe("test-soup", "Crème Tomato Soup", "French", None)
        self.soup.update(ingredients=[{"name": "dressing", "original_text": "dressing with peanut oil", "quantity": "", "unit": "", "notes": ""}], allergens=[], categories=["Soup"], difficulty="")
        self.store.import_records([self.pasta, self.soup])

    def tearDown(self):
        self.temp.cleanup()

    def test_fts_matches_multiple_prefixes_and_accents_without_executing_syntax(self):
        self.assertEqual(self.store.search({"q": "CREME tom"})["items"][0]["record_id"], "test-soup")
        self.assertEqual(self.store.search({"q": '" OR * NOT ('})["total"], 0)
        self.assertEqual(self.store.search({"q": "---"})["total"], 0)
        self.assertEqual(self.store.stats()["recipes"], 2)

    def test_bilingual_search_preserves_source_titles_and_combines_terms(self):
        vietnamese = sample_recipe("vietnamese-rice", "Cơm cà chua", "Vietnamese")
        vietnamese.update(language="vi", description="", categories=["Món chính"], ingredients=[
            {"name": "cà chua", "original_text": "2 quả cà chua"},
            {"name": "gạo", "original_text": "1 bát gạo"},
        ])
        stew = sample_recipe("bo-kho", "Bò kho", "Vietnamese")
        stew.update(description="", categories=["Stew"], ingredients=[{"name": "beef", "original_text": "500 g beef"}])
        self.store.import_records([vietnamese, stew])
        self.assertEqual({item["record_id"] for item in self.store.search({"q": "cà chua"})["items"]},
                         {"test-pasta", "test-soup", "vietnamese-rice"})
        self.assertEqual(self.store.search({"q": "rice tomato"})["items"][0]["record_id"], "vietnamese-rice")
        self.assertEqual(self.store.search({"q": "mì Ý"})["items"][0]["record_id"], "test-pasta")
        self.assertEqual(self.store.search({"q": "bo kho"})["items"][0]["record_id"], "bo-kho")
        self.assertEqual(self.store.search({"ingredient": "cà chua"})["total"], 2)
        self.assertEqual([item["original_text"] for item in self.store.recipe("vietnamese-rice")["ingredients"]],
                         [item["original_text"] for item in vietnamese["ingredients"]])
        self.assertEqual(normalize_recipe_query("mì Ý cá hồi"), "pasta salmon")
        self.assertEqual(normalize_recipe_query("trứng gà hải sản ớt chanh"), "egg seafood chili lime")

    def test_bilingual_exclusions_filter_ingredients_and_declared_allergens(self):
        milk = sample_recipe("milk-pudding", "Milk Pudding")
        milk.update(ingredients=[{"name": "milk", "original_text": "200 ml milk"}], allergens=["milk"])
        vietnamese = sample_recipe("vietnamese-milk", "Sữa nóng", "Vietnamese")
        vietnamese.update(language="vi", ingredients=[{"name": "sữa", "original_text": "1 ly sữa"}], allergens=[])
        peanut = sample_recipe("peanut-sauce", "Sốt đậu phộng", "Vietnamese")
        peanut.update(language="vi", ingredients=[{"name": "đậu phộng", "original_text": "50 g đậu phộng"}], allergens=[])
        milkshake = sample_recipe("milkshake", "Milkshake")
        milkshake.update(ingredients=[{"name": "milkshake", "original_text": "1 cup milkshake"}], allergens=[])
        self.store.import_records([milk, vietnamese, peanut, milkshake])
        for term in ("milk", "sữa", "sua"):
            with self.subTest(term=term):
                ids = {item["record_id"] for item in self.store.search({"exclude_ingredients": [term]})["items"]}
                self.assertNotIn("milk-pudding", ids)
                self.assertNotIn("vietnamese-milk", ids)
                self.assertNotIn("milkshake", ids)
                self.assertIn("test-pasta", ids)
                self.assertEqual(self.store.eligible(["milk-pudding", "vietnamese-milk"], {"exclude_ingredients": [term]}), [])
        for term in ("peanut", "đậu phộng", "dau phong", "lạc"):
            with self.subTest(term=term):
                ids = {item["record_id"] for item in self.store.search({"exclude_ingredients": [term]})["items"]}
                self.assertNotIn("peanut-sauce", ids)
                self.assertNotIn("test-soup", ids)
        self.assertEqual(self.store.search({"q": "peanut sauce"})["items"][0]["record_id"], "peanut-sauce")

    def test_short_exclusion_aliases_do_not_match_inside_unrelated_words(self):
        pepper = sample_recipe("pepper", "Pepper Bowl")
        pepper.update(ingredients=[{"name": "black pepper", "original_text": "black pepper"}], allergens=[])
        cashew = sample_recipe("cashew", "Cashew Bowl")
        cashew.update(ingredients=[{"name": "cashew", "original_text": "cashew"}], allergens=[])
        self.store.import_records([pepper, cashew])
        for exclusion in ("peanut", "lạc", "fish", "cá"):
            with self.subTest(exclusion=exclusion):
                ids = {item["record_id"] for item in self.store.search({"exclude_ingredients": [exclusion]})["items"]}
                self.assertIn("pepper", ids)
                self.assertIn("cashew", ids)

    def test_exact_filters_combine_with_exclusions_and_unknown_values(self):
        self.assertEqual(self.store.search({"country": "Italian", "category": "Pasta", "difficulty": "Easy", "ingredient": "tomato"})["total"], 1)
        self.assertEqual(self.store.search({"max_minutes": 30})["total"], 1)
        self.assertEqual(self.store.search({"require_allergens": True})["total"], 1)
        self.assertEqual(self.store.search({"exclude_ingredients": ["peanut", "wheat"]})["total"], 0)
        self.assertEqual(self.store.search({"sort": "time"})["items"][-1]["record_id"], "test-soup")

    def test_bound_parameters_and_stable_pagination(self):
        self.assertEqual(self.store.search({"country": "Italian' OR 1=1 --"})["total"], 0)
        first = self.store.search(page=1, page_size=1)
        second = self.store.search(page=2, page_size=1)
        self.assertNotEqual(first["items"][0]["record_id"], second["items"][0]["record_id"])
        self.assertEqual(self.store.search(page=999, page_size=1)["page"], 2)
        self.assertEqual(self.store.search({"q": "missing"}, page=999)["page"], 1)

    def test_provider_versions_remain_separate_and_updates_replace_fts(self):
        other = sample_recipe("second-provider", self.pasta["title"])
        self.store.import_records([other])
        self.assertEqual(self.store.search({"q": "pasta"})["total"], 2)
        updated = copy.deepcopy(other)
        updated.update(title="Lentil bowl", description="Lentils", categories=["Rice"], ingredients=[{"name": "lentil", "original_text": "1 cup lentils"}])
        self.assertEqual(self.store.import_records([updated])["updated"], 1)
        self.assertEqual(self.store.search({"q": "lentil"})["items"][0]["record_id"], "second-provider")
        self.assertEqual(self.store.search({"q": "pasta"})["total"], 1)
        canonical = self.store.recipe("second-provider")
        self.assertEqual(self.store.import_records([canonical])["unchanged"], 1)

    def test_bad_import_is_atomic_and_validates_provenance_and_field_types(self):
        bad = sample_recipe("bad")
        bad["source_url"] = ""
        with self.assertRaisesRegex(ValueError, "source_url"):
            self.store.import_records([sample_recipe("new"), bad], replace=True)
        self.assertEqual(self.store.stats()["recipes"], 2)
        self.assertIsNone(self.store.recipe("new"))
        for changes in ({"total_minutes": True}, {"allergens": "wheat"}, {"schema_version": 99}, {"ingredients": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.store.import_records([{**self.pasta, **changes}])

    def test_authoritative_manifest_omits_stale_outputs_and_prunes_database(self):
        processed = self.root / "processed"
        recipes = processed / "recipes" / "test"
        recipes.mkdir(parents=True)
        (recipes / "keep.json").write_text(json.dumps(self.pasta), encoding="utf-8")
        (recipes / "stale.json").write_text(json.dumps(self.soup), encoding="utf-8")
        (processed / "quality_report.json").write_text(json.dumps({"processed_files": ["recipes/test/keep.json"]}), encoding="utf-8")
        result = self.store.import_processed(processed)
        self.assertEqual(result["removed"], 1)
        self.assertIsNone(self.store.recipe("test-soup"))
        self.assertEqual(self.store.search({"q": "creme"})["total"], 0)
        (processed / "quality_report.json").write_text(json.dumps({"processed_files": ["../outside.json"]}), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inside recipes"):
            self.store.import_processed(processed)
        self.assertEqual(self.store.stats()["recipes"], 1)

    def test_filter_validation_and_facets(self):
        for value in ({"require_allergens": "false"}, {"sort": "injected SQL"}, {"max_minutes": -1}, {"max_minutes": True}, {"exclude_ingredients": "peanut"}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse_filters(value)
        self.assertEqual(self.store.facets()["difficulties"], ["Easy"])
        self.assertEqual(self.store.facets()["countries"], ["French", "Italian"])
