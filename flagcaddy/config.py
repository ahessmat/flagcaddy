from __future__ import annotations

import os
import shlex
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


DEFAULT_CONFIG = {
    "llm": {
        "command": "",
        "novelty_threshold": 1.4,
        "cooldown_seconds": 90,
        "batch_size": 5,
        "max_chars": 6000,
    }
}


@dataclass
class AppConfig:
    base_dir: Path
    db_path: Path
    config_path: Path
    llm_command: Optional[List[str]]
    novelty_threshold: float
    llm_cooldown_seconds: int
    llm_batch_size: int
    llm_max_chars: int


def _ensure_base_dir() -> Path:
    root = Path(os.environ.get("FLAGCADDY_HOME", Path.home() / ".flagcaddy"))
    root.mkdir(parents=True, exist_ok=True)
    return root


def _maybe_seed_config(config_path: Path) -> None:
    if config_path.exists():
        return
    template = textwrap.dedent(
        """
        [llm]
        # Command to execute when Flagcaddy needs LLM-backed recommendations.
        # Leave blank to disable automatic LLM calls. Example:
        # command = "codex exec --model gpt-4o-mini"
        command = ""

        # Novelty score needed before Flagcaddy triggers the LLM dispatcher.
        novelty_threshold = 1.4

        # Minimum number of seconds between LLM dispatches per session.
        cooldown_seconds = 90

        # Maximum number of recent events passed into a single LLM prompt.
        batch_size = 5

        # Hard cap on characters concatenated into the `codex exec` prompt.
        max_chars = 6000
        """
    ).strip()
    config_path.write_text(template + "\n", encoding="utf-8")


def _load_config(path: Path) -> dict:
    if not path.exists():
        return DEFAULT_CONFIG
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    return data


def load_config() -> AppConfig:
    base = _ensure_base_dir()
    config_path = base / "config.toml"
    _maybe_seed_config(config_path)
    data = _load_config(config_path)
    llm_section = data.get("llm", {})
    cmd_raw = llm_section.get("command", "").strip()
    llm_command = shlex.split(cmd_raw) if cmd_raw else None
    return AppConfig(
        base_dir=base,
        db_path=base / "state.db",
        config_path=config_path,
        llm_command=llm_command,
        novelty_threshold=float(llm_section.get("novelty_threshold", 1.4)),
        llm_cooldown_seconds=int(llm_section.get("cooldown_seconds", 90)),
        llm_batch_size=int(llm_section.get("batch_size", 5)),
        llm_max_chars=int(llm_section.get("max_chars", 6000)),
    )


__all__ = [
    "AppConfig",
    "load_config",
]

