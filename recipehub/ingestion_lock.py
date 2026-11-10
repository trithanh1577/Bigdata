from __future__ import annotations

import errno
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


_registry_guard = threading.Lock()
_thread_locks: dict[str, threading.RLock] = {}
_held = threading.local()


@contextmanager
def ingestion_lock(processed_dir: Path) -> Iterator[None]:
    """Serialize updates to one data lake across threads and server/CLI processes.

    Nested pipeline stages reuse the current thread's lock. The OS releases the
    file lock automatically if a process exits; the small lock file can remain.
    """
    directory = Path(processed_dir).resolve()
    key = os.path.normcase(str(directory))
    with _registry_guard:
        thread_lock = _thread_locks.setdefault(key, threading.RLock())
    with thread_lock:
        held = getattr(_held, "paths", None)
        if held is None:
            held = _held.paths = set()
        if key in held:
            yield
            return
        directory.mkdir(parents=True, exist_ok=True)
        with (directory / ".ingestion.lock").open("a+b") as handle:
            if os.name == "nt":
                import msvcrt

                handle.seek(0, os.SEEK_END)
                if handle.tell() == 0:
                    handle.write(b"\0")
                    handle.flush()
                while True:
                    handle.seek(0)
                    try:
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                        break
                    except OSError as exc:
                        if exc.errno not in {errno.EACCES, errno.EAGAIN, errno.EDEADLK}:
                            raise
                        time.sleep(0.05)
            else:
                import fcntl

                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            held.add(key)
            try:
                yield
            finally:
                held.remove(key)
                if os.name == "nt":
                    handle.seek(0)
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
