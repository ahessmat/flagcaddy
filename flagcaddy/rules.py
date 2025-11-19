from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional

from .analysis import Fact


@dataclass
class EventContext:
    command: str
    output: str
    facts: List[Fact]
    novelty: float


@dataclass
class Recommendation:
    title: str
    body: str


RuleFunc = Callable[[EventContext], Optional[Recommendation]]


class Rule:
    def __init__(self, name: str, func: RuleFunc):
        self.name = name
        self.func = func

    def apply(self, ctx: EventContext) -> Optional[Recommendation]:
        return self.func(ctx)


def _http_rule(ctx: EventContext) -> Optional[Recommendation]:
    if "http" not in ctx.command.lower():
        for fact in ctx.facts:
            if fact.fact_type == "service" and "http" in fact.value:
                break
        else:
            return None
    return Recommendation(
        title="Enumerate HTTP surface",
        body=(
            "Ports running HTTP were detected. Queue up dir/file brute forcing "
            "with gobuster or feroxbuster, review HTTP headers, and consider "
            "screenshot automation to capture states. Pivot into tech-specific "
            "checks (CMS modules, robots.txt, exposed APIs)."
        ),
    )


def _smb_rule(ctx: EventContext) -> Optional[Recommendation]:
    for fact in ctx.facts:
        if fact.fact_type == "service" and "smb" in fact.value.lower():
            return Recommendation(
                title="Dig deeper on SMB",
                body=(
                    "Open SMB shares present. Try smbclient/smbmap for anonymous and "
                    "credentialed access, list shares with enum4linux, and capture "
                    "SMB signing state to evaluate relay potential."
                ),
            )
    return None


def _ftp_rule(ctx: EventContext) -> Optional[Recommendation]:
    text = f"{ctx.command.lower()} {ctx.output.lower()}"
    if "ftp" not in text:
        return None
    if "anonymous login allowed" in text or "230 login successful" in text:
        content = (
            "Anonymous FTP access looks enabled. Mirror the share, search for creds, "
            "and test for writable paths that could lead to web shell placement."
        )
    else:
        content = (
            "FTP detected. If creds are unknown, fire off hydra/medusa with small "
            "credential lists and capture banner versions for known vulns."
        )
    return Recommendation(title="Interrogate FTP", body=content)


def _shell_rule(ctx: EventContext) -> Optional[Recommendation]:
    if "nc " in ctx.command or "shell" in ctx.output.lower():
        return Recommendation(
            title="Stabilize shells",
            body=(
                "Detected reverse shell activity. Immediately upgrade to a "
                "tty-capable session, record TTY rows/cols, and pull down "
                "linpeas/winpeas or equivalent priv-esc checklists."
            ),
        )
    return None


DEFAULT_RULES: List[Rule] = [
    Rule("http-enum", _http_rule),
    Rule("smb-enum", _smb_rule),
    Rule("ftp-enum", _ftp_rule),
    Rule("shell-checklist", _shell_rule),
]


__all__ = ["DEFAULT_RULES", "Recommendation", "EventContext"]

