from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Iterable, List, Sequence


PROMPT_SENTINEL = "[flagcaddy]"

IP_REGEX = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
PORT_REGEX = re.compile(
    r"(?P<port>\d{1,5})/(?P<proto>tcp|udp)\s+(?P<state>open|filtered|closed)\s+(?P<service>[\w\-\.\?]+)",
    re.IGNORECASE,
)
CRED_REGEX = re.compile(r"(user(name)?|login|pass(word)?)\s*[:=]\s*(?P<value>\S+)", re.IGNORECASE)
FLAG_REGEX = re.compile(r"\bflag\{[^\}]+\}", re.IGNORECASE)


@dataclass(frozen=True)
class Fact:
    fact_type: str
    value: str


def normalize_command(command: str) -> str:
    tokens = command.strip().split()
    return " ".join(tokens)


def canonicalize_output(output: str) -> str:
    cleaned = output.replace("\r", "")
    cleaned = re.sub(PROMPT_SENTINEL + r".*", "", cleaned)
    cleaned = IP_REGEX.sub("<IP>", cleaned)
    cleaned = re.sub(r"\d{4,}", "<NUM>", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def fingerprint(command: str, output: str) -> str:
    payload = normalize_command(command).lower() + "|" + canonicalize_output(output).lower()
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()


def extract_facts(command: str, output: str) -> List[Fact]:
    facts: List[Fact] = []
    tool = command.split()
    if tool:
        facts.append(Fact("tool", tool[0].lower()))
    for ip in set(IP_REGEX.findall(output)):
        facts.append(Fact("host", ip))
    for match in PORT_REGEX.finditer(output):
        port = match.group("port")
        proto = match.group("proto")
        service = match.group("service")
        facts.append(Fact("service", f"{proto}/{port}:{service}"))
    for cred in CRED_REGEX.finditer(output):
        facts.append(Fact("credential", cred.group("value")))
    for flag in FLAG_REGEX.findall(output):
        facts.append(Fact("flag", flag))
    return facts


def estimate_novelty(
    duplicate: bool,
    new_fact_hits: int,
    signal_boost: float = 0.0,
) -> float:
    base = 0.15 if duplicate else 0.9
    base += new_fact_hits * 0.6
    base += signal_boost
    return round(min(base, 5.0), 2)


def signal_boost_from_text(command: str, output: str) -> float:
    boost = 0.0
    keywords = [
        "shell",
        "password",
        "flag{",
        "credential",
        "exploit",
        "pwned",
    ]
    lowered = f"{command.lower()} {output.lower()}"
    for kw in keywords:
        if kw in lowered:
            boost += 0.4
    return boost


__all__ = [
    "Fact",
    "PROMPT_SENTINEL",
    "extract_facts",
    "fingerprint",
    "estimate_novelty",
    "normalize_command",
    "signal_boost_from_text",
]

