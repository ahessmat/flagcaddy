from __future__ import annotations

import shutil
import subprocess
from typing import List, Optional


class CodexExecClient:
    def __init__(self, command: Optional[List[str]]):
        self.command = command

    @property
    def enabled(self) -> bool:
        return bool(self.command)

    def run(self, prompt: str) -> str:
        if not self.command:
            return (
                "LLM dispatcher disabled. Configure [llm] command in ~/.flagcaddy/config.toml."
            )
        binary = self.command[0]
        if shutil.which(binary) is None:
            return f"'{binary}' is not on PATH; skipped codex exec call."
        try:
            proc = subprocess.run(
                self.command,
                input=prompt.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                timeout=120,
            )
        except Exception as exc:  # pragma: no cover
            return f"codex exec failed: {exc}"
        if proc.returncode != 0:
            return f"codex exec exited {proc.returncode}: {proc.stderr.decode('utf-8', errors='ignore')}"
        return proc.stdout.decode("utf-8", errors="ignore").strip()


__all__ = ["CodexExecClient"]

