from __future__ import annotations

import datetime as dt
from typing import List, Optional

from .analysis import (
    Fact,
    estimate_novelty,
    extract_facts,
    fingerprint,
    signal_boost_from_text,
)
from .config import AppConfig
from .db import Database, utcnow
from .llm import CodexExecClient
from .rules import DEFAULT_RULES, EventContext, Recommendation, Rule


class RecommendationEngine:
    def __init__(
        self,
        db: Database,
        config: AppConfig,
        llm_client: Optional[CodexExecClient] = None,
    ):
        self.db = db
        self.config = config
        self.llm = llm_client or CodexExecClient(config.llm_command)
        self.rules: List[Rule] = DEFAULT_RULES

    def process_event(
        self,
        session_id: int,
        *,
        command: str,
        raw_input: str,
        raw_output: str,
        started_at: Optional[str],
        finished_at: Optional[str],
    ) -> int:
        fp = fingerprint(command, raw_output)
        existing = self.db.find_event_by_fingerprint(session_id, fp)
        duplicate = existing is not None
        facts = extract_facts(command, raw_output)
        new_fact_hits = 0
        for fact in facts:
            if self.db.add_fact(session_id, fact.fact_type, fact.value):
                new_fact_hits += 1
        novelty = estimate_novelty(
            duplicate=duplicate,
            new_fact_hits=new_fact_hits,
            signal_boost=signal_boost_from_text(command, raw_output),
        )
        event_id = self.db.insert_event(
            session_id,
            command=command,
            raw_input=raw_input,
            raw_output=raw_output,
            fingerprint=fp,
            novelty=novelty,
            duplicate=duplicate,
            started_at=started_at,
            finished_at=finished_at,
        )
        ctx = EventContext(
            command=command,
            output=raw_output,
            facts=facts,
            novelty=novelty,
        )
        for rule in self.rules:
            rec = rule.apply(ctx)
            if rec:
                self._persist_recommendation(session_id, rec, event_id, source="rule")

        if self._should_trigger_llm(session_id, novelty, duplicate):
            prompt = self._build_prompt(session_id)
            if prompt:
                llm_text = self.llm.run(prompt)
                self._persist_recommendation(
                    session_id,
                    Recommendation(
                        title="LLM recommendations",
                        body=llm_text,
                    ),
                    event_id,
                    source="llm",
                )
        return event_id

    def _persist_recommendation(
        self,
        session_id: int,
        recommendation: Recommendation,
        event_id: int,
        source: str,
    ) -> None:
        self.db.add_recommendation(
            session_id,
            source=source,
            title=recommendation.title,
            body=recommendation.body,
            event_ids=[event_id],
        )

    def _should_trigger_llm(self, session_id: int, novelty: float, duplicate: bool) -> bool:
        if not self.llm.enabled:
            return False
        if duplicate:
            return False
        if novelty < self.config.novelty_threshold:
            return False
        last = self.db.last_llm_timestamp(session_id)
        if not last:
            return True
        last_dt = dt.datetime.fromisoformat(last)
        now_dt = dt.datetime.fromisoformat(utcnow())
        delta = (now_dt - last_dt).total_seconds()
        return delta >= self.config.llm_cooldown_seconds

    def _build_prompt(self, session_id: int) -> str:
        rows = list(
            reversed(self.db.recent_events(session_id, limit=self.config.llm_batch_size * 2))
        )
        if not rows:
            return ""
        buffer: List[str] = []
        total_chars = 0
        for row in rows:
            entry = (
                f"Command: {row['command']}\n"
                f"Output:\n{row['raw_output']}\n"
                f"Novelty: {row['novelty']}\n"
                "----\n"
            )
            total_chars += len(entry)
            if total_chars > self.config.llm_max_chars:
                break
            buffer.append(entry)
            if len(buffer) >= self.config.llm_batch_size:
                break
        instructions = (
            "You are a CTF and pentest assistant. Given the transcript chunks above, "
            "summarize the key findings and list 3 concrete next steps. Focus on actionable "
            "enumeration or exploitation guidance."
        )
        payload = "\n".join(buffer) + "\n" + instructions
        return payload


__all__ = ["RecommendationEngine"]

