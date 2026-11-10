from __future__ import annotations

import multiprocessing
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from recipehub.ingestion_lock import ingestion_lock


def _acquire_in_child(directory, ready, acquired):
    ready.set()
    with ingestion_lock(Path(directory)):
        acquired.set()


class IngestionLockTests(unittest.TestCase):
    def test_nested_pipeline_stages_are_reentrant_and_other_threads_wait(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "processed"
            started = threading.Event()
            acquired = threading.Event()

            def other_thread():
                started.set()
                with ingestion_lock(directory):
                    acquired.set()

            with ThreadPoolExecutor(max_workers=1) as pool:
                with ingestion_lock(directory):
                    with ingestion_lock(directory):
                        future = pool.submit(other_thread)
                        self.assertTrue(started.wait(5))
                        self.assertFalse(acquired.wait(0.1))
                future.result(timeout=5)
                self.assertTrue(acquired.is_set())

    def test_scheduler_and_server_processes_share_the_lock(self):
        context = multiprocessing.get_context("spawn")
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "processed"
            ready, acquired = context.Event(), context.Event()
            child = context.Process(target=_acquire_in_child, args=(str(directory), ready, acquired))
            try:
                with ingestion_lock(directory):
                    child.start()
                    self.assertTrue(ready.wait(10))
                    self.assertFalse(acquired.wait(0.15))
                self.assertTrue(acquired.wait(10))
                child.join(timeout=10)
                self.assertEqual(child.exitcode, 0)
            finally:
                if child.is_alive():
                    child.terminate()
                    child.join(timeout=5)

    def test_failed_ingestion_releases_the_lock(self):
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp) / "processed"
            with self.assertRaises(OSError):
                with ingestion_lock(directory):
                    raise OSError("temporary write failure")
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(lambda: self._acquire_once(directory))
                self.assertTrue(future.result(timeout=5))

    @staticmethod
    def _acquire_once(directory):
        with ingestion_lock(directory):
            return True
