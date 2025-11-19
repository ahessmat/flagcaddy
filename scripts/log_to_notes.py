#!/usr/bin/env python3
"""Translate /home/kali/ctf.log into a structured notes.md file."""
from __future__ import annotations

import argparse
import json
import re
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

BASE_DIR = Path(__file__).resolve().parents[1]
LOG_PATH = Path("/home/kali/ctf.log")
STATE_PATH = BASE_DIR / "data/ctf_state.json"
NOTES_PATH = BASE_DIR / "notes.md"
DEFAULT_ENGAGEMENT = {
    "name": "Unset",
    "scope": "",
    "objective": "",
    "last_summary": "",
}
IP_RE = re.compile(r"\\b(?:\\d{1,3}\\.){3}\\d{1,3}\\b")
COMMAND_RE = re.compile(r"^(?P<prompt>[^\n\r]*[$#])\s*(?P<cmd>.+)$")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def load_state() -> Dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {
        "engagement": DEFAULT_ENGAGEMENT,
        "log_offset": 0,
        "timeline": [],
        "hosts": {},
    }


def save_state(state: Dict) -> None:
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True))


def read_new_log_data(offset: int) -> tuple[str, int]:
    if not LOG_PATH.exists():
        return "", offset
    data = LOG_PATH.read_bytes()
    if offset > len(data):
        offset = 0
    return data[offset:].decode(errors="ignore"), len(data)


def iter_command_blocks(chunk: str) -> List[Dict[str, str]]:
    blocks: List[Dict[str, str]] = []
    current: Optional[Dict[str, List[str]]] = None
    for raw_line in chunk.splitlines():
        line = raw_line.rstrip("\r")
        match = COMMAND_RE.match(line)
        if match:
            if current:
                current["output"] = "\n".join(current["output"]).strip()
                blocks.append({"command": current["command"], "output": current["output"]})
            current = {"command": match.group("cmd").strip(), "output": []}
            continue
        if current is None:
            continue
        current["output"].append(line)
    if current:
        current["output"] = "\n".join(current["output"]).strip()
        blocks.append({"command": current["command"], "output": current["output"]})
    return blocks


@dataclass
class CommandSummary:
    summary: str
    details: str
    tags: List[str]
    hosts: List[str]


def summarize_command(cmd: str, output: str, state: Dict) -> CommandSummary:
    lowered = cmd.lower()
    tags: List[str] = []
    hosts = sorted(set(IP_RE.findall(cmd + "\n" + output)))

    if lowered.startswith("nmap"):
        tags.extend(["nmap", "scan"])
        summary = f"Ran Nmap: {cmd}"
        details = parse_nmap_output(output, cmd, state)
        if details:
            details = "Discovered services:\n" + details
        else:
            details = "Nmap executed; waiting on parsed output."
    elif lowered.startswith("ssh"):
        tags.extend(["ssh", "access"])
        summary = f"Attempted SSH: {cmd}"
        details = "Captured SSH attempt for credential tracking."
    elif lowered.startswith("feroxbuster") or lowered.startswith("ffuf"):
        tags.extend(["http", "enum"])
        summary = f"Enumerated web content: {cmd}"
        details = "Web enumeration results captured for later review."
    elif lowered.startswith("gobuster"):
        tags.extend(["http", "enum"])
        summary = f"Ran Gobuster: {cmd}"
        details = "Gobuster output recorded."
    elif lowered.startswith("enum4linux"):
        tags.extend(["smb", "enum"])
        summary = f"Enumerated SMB: {cmd}"
        details = "Enumerated SMB shares or users."
    else:
        summary = f"Command executed: {cmd}"
        details = "Log captured for review."
    if not hosts and tags:
        hosts = infer_hosts_from_state(state)
    return CommandSummary(summary=summary, details=details, tags=tags, hosts=hosts)


def infer_hosts_from_state(state: Dict) -> List[str]:
    if not state.get("hosts"):
        return []
    return sorted(state["hosts"].keys())


def parse_nmap_output(output: str, command: str, state: Dict) -> str:
    lines = output.splitlines()
    collected: List[str] = []
    current_host: Optional[str] = None
    service_section = False
    for line in lines:
        stripped = line.strip()
        if not stripped:
            service_section = False
            continue
        header = re.match(r"Nmap scan report for (.+)", stripped)
        if header:
            current_host = header.group(1).strip()
            register_host(state, current_host)
            collected.append(f"- Host {current_host}")
            service_section = False
            continue
        if stripped.startswith("PORT"):
            service_section = True
            continue
        if service_section and current_host:
            port_match = re.match(r"(?P<port>\d+)/(\w+)\s+(?P<state>\w+)\s+(?P<service>\S+)(\s+(?P<info>.+))?", stripped)
            if not port_match:
                continue
            port = int(port_match.group("port"))
            protocol = port_match.group(2)
            state_name = port_match.group("state")
            service = port_match.group("service")
            info = (port_match.group("info") or "").strip()
            note = info or command
            upsert_service(state, current_host, port, protocol, service, state_name, note)
            entry = f"    - {protocol}/{port} {service} ({state_name})"
            if info:
                entry += f" -> {info}"
            collected.append(entry)
    return "\n".join(collected)


def register_host(state: Dict, host: str) -> None:
    hosts = state.setdefault("hosts", {})
    hosts.setdefault(host, {"notes": [], "services": [], "credentials": []})


def upsert_service(state: Dict, host: str, port: int, protocol: str, service: str, state_name: str, note: str) -> None:
    register_host(state, host)
    services = state["hosts"][host].setdefault("services", [])
    for svc in services:
        if svc["port"] == port and svc["protocol"] == protocol:
            svc.update({"service": service, "state": state_name, "note": note, "updated": utc_now()})
            return
    services.append({
        "port": port,
        "protocol": protocol,
        "service": service,
        "state": state_name,
        "note": note,
        "updated": utc_now(),
    })


def render_notes(state: Dict) -> str:
    lines: List[str] = []
    lines.append("# Engagement Notes")
    lines.append("")
    lines.append(f"_Last generated: {utc_now()}_")
    lines.append("")
    engagement = state.get("engagement", DEFAULT_ENGAGEMENT)
    lines.append("## Overview")
    lines.append(f"- Name: {engagement.get('name', 'Unset')}")
    scope = engagement.get("scope", "") or "(define scope in data/ctf_state.json)"
    objective = engagement.get("objective", "") or "(set objectives in data/ctf_state.json)"
    lines.append(f"- Scope: {scope}")
    lines.append(f"- Objective: {objective}")
    lines.append(f"- Total timeline entries: {len(state.get('timeline', []))}")
    lines.append("")

    lines.append("## Hosts")
    if not state.get("hosts"):
        lines.append("- No hosts recorded yet.")
    else:
        for host, data in sorted(state["hosts"].items()):
            lines.append(f"### {host}")
            notes = data.get("notes") or []
            services = data.get("services") or []
            credentials = data.get("credentials") or []
            if services:
                lines.append("**Services**")
                for svc in sorted(services, key=lambda s: (s["protocol"], s["port"])):
                    note = svc.get("note", "")
                    note_part = f" - {note}" if note else ""
                    lines.append(
                        f"- `{svc['protocol']}/{svc['port']}` {svc['service']} ({svc['state']}){note_part}"
                    )
            else:
                lines.append("- No services captured yet.")
            if credentials:
                lines.append("**Credentials**")
                for cred in credentials:
                    scope = cred.get("scope", "host")
                    lines.append(
                        f"- {cred.get('user')}:{cred.get('password')} (scope: {scope}, source: {cred.get('source', 'manual')})"
                    )
            if notes:
                lines.append("**Notes**")
                for note in notes:
                    lines.append(f"- {note}")
            lines.append("")

    lines.append("## Timeline")
    if not state.get("timeline"):
        lines.append("- No activity recorded yet.")
    else:
        for entry in state["timeline"][-200:]:
            timestamp = entry.get("timestamp", "?")
            summary = entry.get("summary", "")
            command = entry.get("command", "")
            lines.append(f"- [{timestamp}] {summary}")
            lines.append(f"  - Command: `{command}`")
            details = entry.get("details")
            if details:
                for detail_line in details.splitlines():
                    lines.append(f"  - {detail_line}")
            tags = entry.get("tags")
            if tags:
                lines.append(f"  - Tags: {', '.join(tags)}")
            hosts = entry.get("hosts")
            if hosts:
                lines.append(f"  - Hosts: {', '.join(hosts)}")
    lines.append("")
    return "\n".join(lines)


def process_once(state: Dict) -> Dict:
    chunk, new_offset = read_new_log_data(state.get("log_offset", 0))
    state["log_offset"] = new_offset
    if not chunk.strip():
        return state
    blocks = iter_command_blocks(chunk)
    if not blocks:
        return state
    for block in blocks:
        summary = summarize_command(block["command"], block["output"], state)
        state.setdefault("timeline", []).append({
            "timestamp": utc_now(),
            "command": block["command"],
            "summary": summary.summary,
            "details": summary.details,
            "tags": summary.tags,
            "hosts": summary.hosts,
        })
    return state


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loop", action="store_true", help="Continuously watch the log for updates")
    parser.add_argument("--interval", type=int, default=30, help="Polling interval in seconds when --loop is used")
    parser.add_argument("--once", action="store_true", help="Process log once even if no new data is present")
    args = parser.parse_args()

    NOTES_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

    state = load_state()
    if args.once:
        state = process_once(state)
    else:
        state = process_once(state)

    save_state(state)
    NOTES_PATH.write_text(render_notes(state))

    if not args.loop:
        return

    interval = max(5, args.interval)
    while True:
        time.sleep(interval)
        state = load_state()
        state = process_once(state)
        save_state(state)
        NOTES_PATH.write_text(render_notes(state))


if __name__ == "__main__":
    main()
