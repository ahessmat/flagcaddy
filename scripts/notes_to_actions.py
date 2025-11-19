#!/usr/bin/env python3
"""Read notes/state and publish prioritized next steps for the web UI."""
from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List

BASE_DIR = Path(__file__).resolve().parents[1]
STATE_PATH = BASE_DIR / "data/ctf_state.json"
NEXT_STEPS_PATH = BASE_DIR / "data/next_steps.json"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Suggestion:
    priority: int
    title: str
    details: str
    command: str
    host: str | None
    service: str | None
    tags: List[str]

    def to_dict(self, source: str) -> Dict:
        return {
            "priority": self.priority,
            "title": self.title,
            "details": self.details,
            "command": self.command,
            "host": self.host,
            "service": self.service,
            "tags": self.tags,
            "source": source,
            "generated": utc_now(),
        }


SERVICE_TEMPLATES = {
    "http": [
        Suggestion(
            priority=2,
            title="Enumerate HTTP content on {host}:{port}",
            details="Use forced browsing to find hidden directories/endpoints.",
            command=(
                "feroxbuster -u http://{host}:{port}/ -w /usr/share/wordlists/dirbuster/directory-list-2.3-medium.txt"
            ),
            host=None,
            service="http",
            tags=["http", "enum"],
        ),
        Suggestion(
            priority=3,
            title="Grab HTTP technology fingerprints {host}:{port}",
            details="Run whatweb and eyewitness/similar tooling for screenshots.",
            command="whatweb http://{host}:{port}/",
            host=None,
            service="http",
            tags=["http", "fingerprint"],
        ),
    ],
    "https": [
        Suggestion(
            priority=2,
            title="Assess HTTPS service on {host}:{port}",
            details="Inspect certificates, supported ciphers, and directories.",
            command="sslscan {host}:{port}",
            host=None,
            service="https",
            tags=["tls", "https"],
        )
    ],
    "ssh": [
        Suggestion(
            priority=4,
            title="Attempt SSH auth workflows on {host}:{port}",
            details="Try gathered creds or enumerate banner for hints.",
            command="ssh -v user@{host} -p {port}",
            host=None,
            service="ssh",
            tags=["ssh", "access"],
        )
    ],
    "smb": [
        Suggestion(
            priority=2,
            title="Enumerate SMB shares on {host}:{port}",
            details="Use smbclient/enum4linux-ng to query shares and permissions.",
            command="enum4linux-ng -A {host}",
            host=None,
            service="smb",
            tags=["smb", "enum"],
        )
    ],
    "ftp": [
        Suggestion(
            priority=3,
            title="Inspect FTP service on {host}:{port}",
            details="Check anonymous access and banner leakage.",
            command="ftp {host} {port}",
            host=None,
            service="ftp",
            tags=["ftp", "enum"],
        )
    ],
}

GLOBAL_SUGGESTIONS = [
    Suggestion(
        priority=1,
        title="Update engagement scope/objectives",
        details="Populate data/ctf_state.json -> engagement.{name,scope,objective} for better reporting.",
        command="",
        host=None,
        service=None,
        tags=["planning"],
    )
]


def load_state() -> Dict:
    if not STATE_PATH.exists():
        return {}
    return json.loads(STATE_PATH.read_text())


def normalize_service_name(service: str) -> str:
    if not service:
        return ""
    service = service.lower()
    if service in {"ssl/http", "https"}:
        return "https"
    if service in {"ms-wbt-server", "rdp"}:
        return "rdp"
    return service


def generate_service_suggestions(host: str, service: Dict) -> Iterable[Suggestion]:
    name = normalize_service_name(service.get("service", ""))
    templates = SERVICE_TEMPLATES.get(name)
    if not templates:
        return []
    for template in templates:
        yield Suggestion(
            priority=template.priority,
            title=template.title.format(host=host, port=service.get("port")),
            details=template.details.format(host=host, port=service.get("port")),
            command=template.command.format(host=host, port=service.get("port")),
            host=host,
            service=name,
            tags=template.tags,
        )


def consolidate_suggestions(state: Dict) -> List[Dict]:
    suggestions: List[Dict] = []
    timeline_entries = state.get("timeline", [])
    if not state.get("engagement"):
        suggestions.extend([s.to_dict("global") for s in GLOBAL_SUGGESTIONS])
    else:
        engagement = state["engagement"]
        if not engagement.get("scope") or not engagement.get("objective"):
            suggestions.append(GLOBAL_SUGGESTIONS[0].to_dict("global"))
    for host, data in (state.get("hosts") or {}).items():
        for service in data.get("services", []):
            for suggestion in generate_service_suggestions(host, service):
                suggestions.append(suggestion.to_dict("service"))
        if not data.get("services"):
            suggestions.append(
                Suggestion(
                    priority=2,
                    title=f"Collect service inventory for {host}",
                    details="Run a more aggressive nmap scan to populate services.",
                    command=f"nmap -sCV -p- {host}",
                    host=host,
                    service=None,
                    tags=["scan"],
                ).to_dict("host")
            )
    if timeline_entries:
        last_entry = timeline_entries[-1]
        suggestions.append(
            Suggestion(
                priority=5,
                title="Review last action",
                details=f"Latest command `{last_entry.get('command')}` ran at {last_entry.get('timestamp')}. Confirm artifacts saved.",
                command="",
                host=None,
                service=None,
                tags=["review"],
            ).to_dict("timeline")
        )
    suggestions.sort(key=lambda item: item["priority"])
    return suggestions


def write_next_steps(payload: List[Dict]) -> None:
    NEXT_STEPS_PATH.parent.mkdir(parents=True, exist_ok=True)
    NEXT_STEPS_PATH.write_text(json.dumps({"generated": utc_now(), "items": payload}, indent=2))


def cycle_once() -> None:
    state = load_state()
    suggestions = consolidate_suggestions(state)
    write_next_steps(suggestions)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="Continuously refresh next-step suggestions")
    parser.add_argument("--interval", type=int, default=60, help="Interval seconds when looping")
    args = parser.parse_args()

    cycle_once()
    if not args.loop:
        return

    interval = max(10, args.interval)
    while True:
        time.sleep(interval)
        cycle_once()


if __name__ == "__main__":
    main()
