"""Central configuration loader. YAML files + environment variables.

Everything configurable lives outside core code so users can tune the
radar without editing Python.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

try:
    import yaml
except ImportError:  # pragma: no cover - requirements guarantee pyyaml
    yaml = None

ROOT = Path(__file__).resolve().parent.parent


def _load_yaml(path: Path) -> Dict[str, Any]:
    if not path.exists() or yaml is None:
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_dotenv(root: Path) -> None:
    """Minimal .env loader (no extra dependency). Sets vars missing from env.
    The .env file is gitignored and never committed."""
    path = root / ".env"
    if not path.exists():
        return
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("'\"")
            if key and key not in os.environ:
                os.environ[key] = val
    except Exception:
        pass


def load_config(root: Path | None = None) -> Dict[str, Any]:
    """Load sources.yaml + categories.yaml + env overrides into one dict."""
    base = root or ROOT
    _load_dotenv(base)
    sources = _load_yaml(base / "config" / "sources.yaml")
    categories = _load_yaml(base / "config" / "categories.yaml")

    def _int(name: str, default: int) -> int:
        try:
            return int(os.getenv(name, str(default)))
        except ValueError:
            return default

    cfg: Dict[str, Any] = {
        "root": str(base),
        "sources": sources,
        "categories": categories.get("categories", []),
        "keywords": categories.get("keywords", {}),
        "telegram_bot_token": os.getenv("TELEGRAM_BOT_TOKEN", ""),
        "telegram_chat_id": os.getenv("TELEGRAM_CHAT_ID", ""),
        "telegram_min_score": _int("TELEGRAM_MIN_SCORE", 75),
        "daily_digest": os.getenv("DAILY_DIGEST", "false").lower() in ("1", "true", "yes"),
        "gemini_api_key": os.getenv("GEMINI_API_KEY", ""),
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "retention_days": _int("RETENTION_DAYS", 90),
        "youtube_api_key": os.getenv("YOUTUBE_API_KEY", ""),
        "github_token": os.getenv("GITHUB_TOKEN", ""),
    }
    return cfg
