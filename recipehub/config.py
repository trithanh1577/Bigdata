from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_local_env() -> None:
    """Read simple KEY=value settings from .env without adding a dependency."""
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


_load_local_env()


@dataclass(frozen=True)
class Settings:
    project_root: Path = PROJECT_ROOT
    sources_file: Path = PROJECT_ROOT / "config" / "recipe_sources.json"
    raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    state_dir: Path = PROJECT_ROOT / "data" / "state"
    user_agent: str = os.getenv(
        "CRAWLER_USER_AGENT", "GlobalCulinaryKnowledgeBase/1.0 (student project)"
    )
    timeout_seconds: int = int(os.getenv("CRAWLER_TIMEOUT_SECONDS", "25"))
    delay_seconds: float = float(os.getenv("CRAWLER_DELAY_SECONDS", "1.5"))

    def ensure_directories(self) -> None:
        for path in (self.raw_dir, self.processed_dir, self.state_dir):
            path.mkdir(parents=True, exist_ok=True)

    def load_sources(self) -> list[dict[str, object]]:
        sources = json.loads(self.sources_file.read_text(encoding="utf-8"))
        return [source for source in sources if source.get("enabled", True)]
