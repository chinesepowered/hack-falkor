"""Deterministic entity linking: find mentions of known entities in free text.

Aliases come from the dataset (people, services, APIs, customers, docs). Keys such as
SUP-298, INC-142, PR #881 and ADR-007 are matched with patterns against the ids that exist.
"""
from __future__ import annotations

import re

KEY_RE = re.compile(r"\b((?:SUP|PLAT|PAY|DATA|GROW|DEVREL)-\d+)\b")
INC_RE = re.compile(r"\b(INC-\d+)\b")
PR_RE = re.compile(r"(?:\bPRs?\s*)?#(\d{3})\b")
ADR_RE = re.compile(r"\bADR-0*(\d+)\b")
V1_RE = re.compile(r"(?<![\w.])v1(?!\w|\.\d)")
V2_RE = re.compile(r"(?<![\w.])v2(?!\w|\.\d)")


class Linker:
    def __init__(self) -> None:
        self._patterns: list[tuple[re.Pattern, str]] = []
        self.known: set[str] = set()

    def add(self, entity_id: str, aliases: list[str], case_sensitive: bool = False) -> None:
        self.known.add(entity_id)
        for alias in aliases:
            if not alias:
                continue
            flags = 0 if case_sensitive else re.IGNORECASE
            pat = re.compile(r"(?<![\w-])" + re.escape(alias) + r"(?![\w-])", flags)
            self._patterns.append((pat, entity_id))

    def register(self, entity_id: str) -> None:
        """Make an id linkable through the key patterns (tickets, incidents, PRs, ADR docs)."""
        self.known.add(entity_id)

    def link(self, text: str, exclude: set[str] | None = None) -> list[str]:
        """Return the entity ids mentioned in text, ordered by first appearance."""
        found: dict[str, int] = {}

        def hit(eid: str, pos: int) -> None:
            if eid in self.known and (not exclude or eid not in exclude):
                found.setdefault(eid, pos)

        for pat, eid in self._patterns:
            m = pat.search(text)
            if m:
                hit(eid, m.start())
        for m in KEY_RE.finditer(text):
            hit(f"ticket:{m.group(1)}", m.start())
        for m in INC_RE.finditer(text):
            hit(f"inc:{m.group(1)}", m.start())
        for m in PR_RE.finditer(text):
            hit(f"pr:{m.group(1)}", m.start())
        for m in ADR_RE.finditer(text):
            hit(f"doc:adr-{int(m.group(1)):03d}", m.start())
        m = V1_RE.search(text)
        if m:
            hit("api:rest-v1", m.start())
        m = V2_RE.search(text)
        if m:
            hit("api:rest-v2", m.start())
        return sorted(found, key=found.get)
