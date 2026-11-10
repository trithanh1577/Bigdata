from __future__ import annotations

import copy
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from recipehub.knowledge_base import KnowledgeBase
from recipehub.seed import export_seed, load_seed, merge_recipe_records, seed_path
from tests.helpers import offline_settings, sample_recipe


class SeedTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = replace(offline_settings(self.root), database_path=self.root / "recipes.sqlite3")
        self.store = KnowledgeBase(self.settings.database_path)

    def test_export_roundtrip_preserves_recipe_sources_and_omits_private_data(self):
        recipes = [sample_recipe("z-last", "Soup"), sample_recipe("a-first", "Pasta")]
        recipes[0]["instructions"] = ["Nấu súp theo công thức gốc."]
        self.store.import_records(recipes)
        with self.store.connect() as db:
            db.execute("INSERT INTO chat_sessions VALUES (?, ?, ?)", ("private-session-token", 1, '{"history":"private-chat-message"}'))
        (self.root / ".env").write_text("RECIPEHUB_LLM_API_KEY=private-key-marker", encoding="utf-8")
        before = self.store.stats()

        summary = export_seed(self.settings)

        self.assertEqual(summary["recipe_count"], 2)
        self.assertEqual(Path(summary["output"]), seed_path(self.settings))
        self.assertEqual(load_seed(seed_path(self.settings)), sorted(recipes, key=lambda item: item["record_id"]))
        exported = seed_path(self.settings).read_text(encoding="utf-8")
        for marker in ("private-session-token", "private-chat-message", "private-key-marker", "chat_sessions"):
            self.assertNotIn(marker, exported)
        self.assertIn("Nấu súp", exported)
        self.assertEqual(self.store.stats(), before)
        with self.store.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM chat_sessions").fetchone()[0], 1)

    def test_empty_or_invalid_database_preserves_previous_export(self):
        output = self.root / "seed.json"
        original = "previous working seed"
        output.write_text(original, encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "at least one"):
            export_seed(self.settings, output)
        self.assertEqual(output.read_text(encoding="utf-8"), original)
        self.store.import_records([sample_recipe()])
        with self.store.connect() as db:
            db.execute("UPDATE recipes SET payload=?", ('{"schema_version":999}',))
        with self.assertRaises(ValueError):
            export_seed(self.settings, output)
        self.assertEqual(output.read_text(encoding="utf-8"), original)

    def test_failed_atomic_replace_keeps_previous_seed_and_removes_temporary(self):
        self.store.import_records([sample_recipe()])
        output = self.root / "seed.json"
        output.write_text("previous working seed", encoding="utf-8")
        with patch("recipehub.seed.os.replace", side_effect=OSError("temporary filesystem failure")):
            with self.assertRaises(OSError):
                export_seed(self.settings, output)
        self.assertEqual(output.read_text(encoding="utf-8"), "previous working seed")
        self.assertEqual(list(self.root.glob(".seed.json.*.tmp")), [])

    def test_missing_database_is_not_created_by_export(self):
        missing = replace(self.settings, database_path=self.root / "missing.sqlite3")
        with self.assertRaisesRegex(ValueError, "No recipe database"):
            export_seed(missing)
        self.assertFalse(missing.database_path.exists())

    def test_export_cannot_replace_the_database(self):
        self.store.import_records([sample_recipe()])
        with self.assertRaisesRegex(ValueError, "must not replace"):
            export_seed(self.settings, self.settings.database_path)
        self.assertEqual(self.store.stats()["recipes"], 1)

    def test_load_validates_complete_bundle_before_returning_records(self):
        path = self.root / "seed.json"
        recipe = sample_recipe()
        valid = {"format_version": 1, "recipe_count": 1, "recipes": [recipe]}
        invalid_recipe = copy.deepcopy(recipe)
        invalid_recipe["schema_version"] = 999
        cases = [
            [],
            {**valid, "format_version": 2},
            {**valid, "format_version": True},
            {**valid, "recipe_count": True},
            {**valid, "recipe_count": 2},
            {**valid, "recipe_count": 0, "recipes": []},
            {**valid, "recipe_count": 2, "recipes": [recipe, recipe]},
            {**valid, "recipe_count": 2, "recipes": [recipe, invalid_recipe]},
            {**valid, "api_key": "unexpected-field"},
        ]
        for bundle in cases:
            with self.subTest(bundle_keys=list(bundle) if isinstance(bundle, dict) else "array"):
                path.write_text(json.dumps(bundle), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_seed(path)
        path.write_text(json.dumps(valid), encoding="utf-8")
        self.assertEqual(load_seed(path), [recipe])

    def test_load_rejects_nonfinite_numbers_and_duplicate_json_fields(self):
        path = self.root / "seed.json"
        for content in ('{"format_version":1,"format_version":1}', '{"format_version":1,"recipe_count":NaN}'):
            with self.subTest(content=content):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_seed(path)

    def test_merge_compares_source_instants_before_processed_time_and_sorts_ids(self):
        older = sample_recipe("shared", "Older source snapshot")
        older.update(collected_at="2026-11-09T04:00:00+00:00", processed_at="2026-11-09T06:00:00+00:00")
        newer = sample_recipe("shared", "Newer source snapshot")
        newer.update(collected_at="2026-11-09T12:00:00+07:00", processed_at="2026-11-09T05:30:00+00:00")
        records = merge_recipe_records([sample_recipe("z-last"), newer], [older, sample_recipe("a-first")])
        self.assertEqual([record["record_id"] for record in records], ["a-first", "shared", "z-last"])
        self.assertEqual(records[1]["title"], "Newer source snapshot")
        self.assertEqual(older["title"], "Older source snapshot", "Merging must not change either input batch")

    def test_merge_uses_processed_timestamp_then_later_batch_for_equal_versions(self):
        first = sample_recipe("shared", "First")
        first.update(collected_at="2026-11-09T05:00:00Z", processed_at="2026-11-09T06:00:00+00:00")
        processed_later = {**first, "title": "Processed later", "processed_at": "2026-11-09T14:00:00+07:00"}
        exact_tie = {**processed_later, "title": "Later batch wins"}
        self.assertEqual(merge_recipe_records([processed_later], [first])[0]["title"], "Processed later")
        self.assertEqual(merge_recipe_records([processed_later], [exact_tie])[0]["title"], "Later batch wins")

    def test_merge_tolerates_invalid_dates_and_accepts_empty_batches(self):
        old = sample_recipe("shared", "Invalid date")
        old.update(collected_at="unknown", processed_at="unknown")
        new = sample_recipe("shared", "Valid newer date")
        self.assertEqual(merge_recipe_records([new], [old])[0]["title"], "Valid newer date")
        self.assertEqual(merge_recipe_records([], [old], [{**old, "title": "Last invalid-date version"}])[0]["title"], "Last invalid-date version")
        self.assertEqual(merge_recipe_records([], []), [])
