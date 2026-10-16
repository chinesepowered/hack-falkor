"""Load the synthetic Tallybird sources (YAML exports + Markdown docs and meeting notes)."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from . import config

DOC_ALIASES = {
    "doc:api-quickstart": ["API Quickstart", "quickstart"],
    "doc:webhook-guide": ["Webhook integration guide", "webhook guide"],
    "doc:ledger-runbook": ["ledger runbook", "ledger-service runbook"],
    "doc:auth-runbook": ["auth-service runbook", "auth runbook"],
    "doc:oauth-migration": ["OAuth migration guide", "migration guide"],
    "doc:oncall-handbook": ["On-call handbook"],
    "doc:ubb-onepager": ["one-pager"],
    "doc:event-topics": ["topics catalog"],
    "doc:pm-142": ["INC-142 postmortem"],
    "doc:pm-118": ["INC-118 postmortem"],
    "doc:python-sdk-readme": ["Python SDK README"],
    "doc:partner-onboarding": ["Partner onboarding checklist"],
    "doc:support-macro-keys": ["rotation macro", "API key rotation macro"],
    "doc:eng-onboarding": ["Engineering onboarding"],
    "doc:q4-okrs": ["Q4 OKRs"],
}


@dataclass
class MarkdownSource:
    meta: dict
    body: str
    path: str


@dataclass
class Dataset:
    org: dict
    messages: list[dict]
    tickets: list[dict]
    prs: list[dict]
    events: list[dict]
    docs: list[MarkdownSource] = field(default_factory=list)
    meetings: list[MarkdownSource] = field(default_factory=list)

    @property
    def people(self) -> dict[str, dict]:
        return {p["id"]: p for p in self.org["people"]}


def _read_md(path: Path) -> MarkdownSource:
    text = path.read_text()
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        raise ValueError(f"missing front matter: {path}")
    return MarkdownSource(meta=yaml.safe_load(m.group(1)), body=m.group(2).strip(),
                          path=str(path.relative_to(config.ROOT)))


def load(data_dir: Path | None = None) -> Dataset:
    d = data_dir or config.DATA_DIR
    org = yaml.safe_load((d / "org.yaml").read_text())
    gen_path = d / "generated.yaml"
    gen = yaml.safe_load(gen_path.read_text()) if gen_path.exists() else {}
    ds = Dataset(
        org=org,
        messages=yaml.safe_load((d / "slack.yaml").read_text())["messages"] + gen.get("messages", []),
        tickets=yaml.safe_load((d / "tickets.yaml").read_text())["tickets"] + gen.get("tickets", []),
        prs=yaml.safe_load((d / "prs.yaml").read_text())["prs"] + gen.get("prs", []),
        events=yaml.safe_load((d / "events.yaml").read_text())["events"],
    )
    ds.docs = [_read_md(p) for p in sorted((d / "docs").glob("*.md"))]
    ds.meetings = [_read_md(p) for p in sorted((d / "meetings").glob("*.md"))]
    return ds


def _clean(s: str) -> str:
    s = re.sub(r"\*\*|__|`", "", s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def split_claims(body: str) -> list[str]:
    """Split a Markdown body into short factual statements (sentences, bullets, table rows)."""
    out: list[str] = []
    heading = ""
    in_code = False
    lines = body.splitlines()
    for i, raw in enumerate(lines):
        line = raw.strip()
        if line.startswith("```"):
            in_code = not in_code
            continue
        if in_code or not line:
            continue
        if line.startswith("#"):
            heading = _clean(line.lstrip("#"))
            continue
        if line.startswith("|"):
            cells = [_clean(c) for c in line.strip("|").split("|")]
            if all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                continue
            nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
            if nxt.startswith("|") and re.search(r"-{2,}", nxt):
                continue  # header row
            out.append(f"{heading}: " + " — ".join(c for c in cells if c) if heading else " — ".join(cells))
            continue
        line = re.sub(r"^([-*]|\d+\.)\s+", "", line)
        for sent in re.split(r"(?<=[.!?])\s+(?=[A-Z`*(])", _clean(line)):
            if len(sent.split()) >= 5:
                out.append(sent)
    return out
