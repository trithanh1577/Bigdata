from __future__ import annotations

import io
import json
import shutil
import tempfile
import threading
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

from recipehub import cli
from recipehub.knowledge_base import KnowledgeBase
from recipehub.normalize import NormalizationPipeline
from recipehub.seed import export_seed, seed_path
from recipehub.server import RecipeServer
from tests.helpers import offline_settings, sample_recipe


class SeedStartupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def settings(self, name):
        root = self.root / name
        return replace(offline_settings(root), database_path=root / "data" / "recipes.sqlite3")

    def write_bundle(self, path, records):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"format_version": 1, "recipe_count": len(records), "recipes": records}), encoding="utf-8")

    def prepare(self, settings):
        with patch("sys.stdout", io.StringIO()):
            return cli._prepare_store(settings)

    def test_export_then_copy_only_seed_restores_http_collection_and_restart_is_idempotent(self):
        local = self.settings("local")
        original = [sample_recipe(), sample_recipe("ginger-rice", "Ginger Rice", "Japanese")]
        KnowledgeBase(local.database_path).import_records(original)
        export_seed(local)
        deployed = self.settings("deployed")
        seed_path(deployed).parent.mkdir(parents=True)
        shutil.copyfile(seed_path(local), seed_path(deployed))
        self.assertFalse(deployed.database_path.exists())
        self.assertFalse(deployed.raw_dir.exists())
        self.assertFalse(deployed.processed_dir.exists())

        store = self.prepare(deployed)
        self.assertEqual(store.stats()["recipes"], 2)
        frontend = Path(__file__).resolve().parents[1] / "frontend"
        server = RecipeServer(("127.0.0.1", 0), store, frontend, settings=deployed)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urlopen(base + "/api/v1/health", timeout=5) as response:
                self.assertEqual(json.load(response)["recipes"], 2)
            with urlopen(base + "/api/v1/recipes/test-pasta", timeout=5) as response:
                detail = json.load(response)
            self.assertEqual(detail["source_url"], original[0]["source_url"])
            self.assertEqual(detail["ingredients"], original[0]["ingredients"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)
        restarted = self.prepare(deployed)
        self.assertEqual(restarted.stats()["recipes"], 2)
        self.assertEqual(restarted.recipe("ginger-rice")["title"], "Ginger Rice")

    def test_seed_update_adds_and_updates_without_removing_runtime_or_newer_versions(self):
        settings = self.settings("updates")
        baseline = [sample_recipe("updated", "Old seed"), sample_recipe("newer", "Original seed")]
        self.write_bundle(seed_path(settings), baseline)
        store = self.prepare(settings)
        runtime = sample_recipe("runtime-extra", "Collected on server")
        newer = {**baseline[1], "title": "Newer server snapshot", "collected_at": "2026-11-12T05:00:00+00:00"}
        store.import_records([runtime, newer])
        updated = {**baseline[0], "title": "Updated shipped recipe", "collected_at": "2026-11-10T12:00:00+07:00"}
        older_than_runtime = {**baseline[1], "title": "Older shipped version", "collected_at": "2026-11-10T05:00:00+00:00"}
        self.write_bundle(seed_path(settings), [updated, older_than_runtime, sample_recipe("seed-added", "New shipped recipe")])

        restored = self.prepare(settings)
        self.assertEqual(restored.stats()["recipes"], 4)
        self.assertEqual(restored.recipe("updated")["title"], "Updated shipped recipe")
        self.assertEqual(restored.recipe("newer")["title"], "Newer server snapshot")
        self.assertEqual(restored.recipe("runtime-extra"), runtime)
        self.assertEqual(self.prepare(settings).stats()["recipes"], 4)

    def test_normalize_then_build_keeps_bundled_recipes_without_raw_copies(self):
        settings = self.settings("pipeline")
        self.write_bundle(seed_path(settings), [sample_recipe("bundled", "Bundled baseline")])
        store = self.prepare(settings)
        raw = settings.raw_dir / "themealdb" / "runs" / "one" / "records" / "record.json"
        raw.parent.mkdir(parents=True)
        raw.write_text(json.dumps({
            "source_id": "themealdb", "source_name": "Test provider", "source_record_id": "new-source-recipe",
            "source_url": "https://provider.test/new-recipe", "source_license": "Test terms",
            "attribution": "Test provider", "collected_at": "2026-11-10T05:00:00+00:00",
            "payload": {"strMeal": "Freshly collected soup", "strIngredient1": "tomato", "strInstructions": "Cook tomatoes."},
        }), encoding="utf-8")
        report = NormalizationPipeline(settings).run()
        self.assertEqual(report["processed"], 1)
        with patch("sys.argv", ["recipehub", "build"]), patch.object(cli, "Settings", return_value=settings), patch("sys.stdout", io.StringIO()):
            cli.main()
        self.assertEqual(store.stats()["recipes"], 2)
        self.assertIsNotNone(store.recipe("bundled"))
        self.assertEqual(self.prepare(settings).stats()["recipes"], 2)
        self.assertEqual(len(list(settings.raw_dir.glob("*/runs/*/records/*.json"))), 1)

    def test_invalid_seed_never_partially_updates_existing_database(self):
        settings = self.settings("invalid")
        store = KnowledgeBase(settings.database_path)
        existing = sample_recipe("existing", "Keep this source record")
        store.import_records([existing])
        invalid = sample_recipe("invalid")
        invalid["source_url"] = ""
        self.write_bundle(seed_path(settings), [sample_recipe("should-not-import"), invalid])

        with self.assertRaises(ValueError):
            store.import_seed(seed_path(settings))
        with self.assertRaises(ValueError):
            self.prepare(settings)
        self.assertEqual(store.stats()["recipes"], 1)
        self.assertEqual(store.recipe("existing"), existing)
        self.assertIsNone(store.recipe("should-not-import"))

    def test_serve_command_prepares_seed_before_starting_server(self):
        settings = self.settings("serve")
        self.write_bundle(seed_path(settings), [sample_recipe()])
        with patch("sys.argv", ["recipehub", "serve", "--host", "0.0.0.0", "--port", "12345"]), patch.object(cli, "Settings", return_value=settings), patch("recipehub.server.serve") as serve, patch("sys.stdout", io.StringIO()):
            cli.main()
        serve.assert_called_once()
        args = serve.call_args.args
        self.assertEqual(args[0].stats()["recipes"], 1)
        self.assertEqual(args[1], settings.project_root / "frontend")
        self.assertEqual(args[2:4], ("0.0.0.0", 12345))

    def test_export_and_import_commands_honor_optional_paths(self):
        settings = self.settings("commands")
        store = KnowledgeBase(settings.database_path)
        store.import_records([sample_recipe()])
        custom_output = self.root / "custom" / "recipes.json"
        with patch("sys.argv", ["recipehub", "export-seed", "--output", str(custom_output)]), patch.object(cli, "Settings", return_value=settings), patch("sys.stdout", io.StringIO()):
            cli.main()
        self.assertTrue(custom_output.is_file())
        self.assertFalse(seed_path(settings).exists())
        self.assertEqual(store.stats()["recipes"], 1)
        self.write_bundle(custom_output, [sample_recipe("imported", "Imported custom recipe")])
        with patch("sys.argv", ["recipehub", "import-seed", "--input", str(custom_output)]), patch.object(cli, "Settings", return_value=settings), patch("sys.stdout", io.StringIO()):
            cli.main()
        self.assertEqual(store.stats()["recipes"], 2)
        self.assertIsNotNone(store.recipe("imported"))


if __name__ == "__main__":
    unittest.main()
