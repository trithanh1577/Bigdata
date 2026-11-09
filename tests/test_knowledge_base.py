import copy
import json
import tempfile
import unittest
from pathlib import Path

from recipehub.knowledge_base import KnowledgeBase, parse_filters
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
