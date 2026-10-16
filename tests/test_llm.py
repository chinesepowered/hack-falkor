"""End-to-end tests that call the configured LLM. Skipped when LLM_API_KEY is not set."""
import pytest

from capybrain import agent, ripple

from .conftest import has_llm

pytestmark = pytest.mark.skipif(not has_llm(), reason="LLM_API_KEY not set")


def run_agent(q):
    events = list(agent.ask(q, use_memory=False))
    answer = [e for e in events if e["type"] == "answer"]
    tools_used = [e["name"] for e in events if e["type"] == "tool_call"]
    return (answer[0]["text"] if answer else ""), tools_used


def test_agent_why_question_uses_decision_trace():
    text, used = run_agent("Why did we move webhooks to a queue?")
    assert "trace_decision" in used
    assert "INC-142" in text or "Tidewater" in text


def test_agent_who_knows_does_not_send_you_to_someone_who_left():
    text, used = run_agent("Who can help me with the ledger service?")
    assert "who_knows" in used
    assert "Marco" in text
    assert "left" in text.lower()


def test_ripple_v1_sunset_finds_orchard_promise(fresh_graph):
    events = list(ripple.ingest("Heads up everyone: we're switching off REST API v1 on December 1st. "
                                "Every customer needs to be on API v2 with OAuth by then.",
                                "person:hannah", "chan:announcements", "2026-10-16T09:30:00Z"))
    kinds = [e["type"] for e in events]
    assert kinds[-1] == "done"
    conflicts = next(e for e in events if e["type"] == "conflicts")["items"]
    assert any(c["id"] == "dec:D-009" and c["relation"] == "conflicts" for c in conflicts)
    stale = next(e for e in events if e["type"] == "stale")["docs"]
    assert "doc:api-quickstart" in {d["doc"]["id"] for d in stale}
    proposals = next(e for e in events if e["type"] == "proposals")["items"]
    owners = {p["assignee"]["name"] for p in proposals if p["kind"] == "service_change" and "auth-service" in p["title"]}
    assert owners == {"Marco Rossi"}
