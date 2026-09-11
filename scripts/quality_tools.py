"""Resolve the exact upstream figure/verification tools used for these results."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCK = ROOT / "tools/quality-tools.lock.json"
CACHE = ROOT / ".local/quality-tools/math-modeling"


def tool_lock() -> dict:
    return json.loads(LOCK.read_text(encoding="utf-8"))


def matches_lock(directory: Path) -> bool:
    for relative, expected in tool_lock()["files"].items():
        path = directory / relative
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            return False
    return True


def resolve_tools() -> Path:
    explicit = os.environ.get("CUMCM_SKILL_ROOT")
    candidates = (
        [Path(explicit)] if explicit else [CACHE, Path.home() / ".codex/skills/math-modeling"]
    )
    for path in candidates:
        if matches_lock(path):
            return path.resolve()
    raise RuntimeError(
        "Pinned quality tools are missing or changed. Run: python scripts/setup_quality_tools.py"
    )


def load_tool(name: str, relative: str):
    path = resolve_tools() / relative
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
