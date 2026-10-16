"""Graph-level tests: no LLM needed. They pin down the storylines the demo relies on and prove
the answers come from relationships in FalkorDB, not from text similarity."""
import pytest

from capybrain import dataset, db, ripple, seed, tools, xray
from capybrain import queries as Q
from capybrain.linker import V1_RE


def test_graph_size_and_labels():
    counts = {r["label"]: r["c"] for r in db.run(Q.STATS, ro=True)}
    for label in ("Person", "Team", "Service", "Api", "Customer", "Decision", "Doc", "Claim", "Message", "Ticket", "PR", "Meeting"):
        assert counts.get(label, 0) > 0, label
    assert sum(counts.values()) > 500
    assert db.run("MATCH ()-[r]->() RETURN count(r) AS c")[0]["c"] > 2000


def test_linker_and_claims():
    lk = tools.linker()
    assert "api:rest-v1" in lk.link("we're switching off REST API v1 on December 1st")
    assert "ticket:SUP-298" in lk.link("see SUP-298")
    assert "doc:adr-007" in lk.link("details in ADR-007")
    assert "person:wei" in lk.link("ask Wei about it")
    assert V1_RE.search("base URL is https://api.tallybird.example/v1.")
    assert not V1_RE.search("released v1.2 today")
    claims = dataset.split_claims("# T\n\n## Escalation\n| Service | Who |\n|---|---|\n| ledger-service | Dana Okafor |\n\nThe ledger reconciles nightly at 02:00 UTC.")
    assert "Escalation: ledger-service — Dana Okafor" in claims
    assert "The ledger reconciles nightly at 02:00 UTC." in claims


def test_decision_trace_webhook_queue():
    row = db.to_json(db.run(Q.DECISION_CORE, {"id": "dec:D-007"}, ro=True))[0]
    assert {p["name"] for p in row["deciders"]} == {"Marco Rossi", "Priya Raman", "Hannah Lee"}
    assert {t["id"] for t in row["triggers"]} == {"inc:INC-142"}
    assert len(row["rejected"]) == 2
    assert {p["id"] for p in row["prs"]} == {"pr:881", "pr:893"}
    assert len(row["evidence"]) == 4


def test_trace_tool_finds_decision_by_meaning():
    res = tools.trace_decision(tools.Ctx(), "why do webhooks go through a queue now")
    assert res.data["decision"]["id"] == "dec:D-007"
    assert any("Tidewater" in e["said"] for e in res.data["evidence"])


def test_who_knows_ledger_skips_people_who_left():
    res = tools.who_knows(tools.Ctx(), "ledger service")
    ask = [p["name"] for p in res.data["people_to_ask"]]
    assert ask[0] == "Marco Rossi"
    assert "Wei Zhang" in ask[:3]
    assert "Dana Okafor" not in ask
    assert res.data["left_the_company"][0]["name"] == "Dana Okafor"
    assert "no active owner" in res.data["warning"]


def test_impact_of_v1_reaches_customers_through_crm_edges():
    res = tools.impact_of(tools.Ctx(), "REST API v1")
    customers = {c["customer"] for c in res.data["customers"]}
    assert customers == {"Bluefin Logistics", "Orchard Health", "Nimbus Retail"}
    services = {s["service"]: s for s in res.data["services"]}
    assert services["auth-service"]["owner_has_left"] is True
    assert {"onboarding-flow", "public-api-gateway", "python-sdk"} <= set(services)
    decisions = {d["decision"].split(":")[0] for d in res.data["decisions_and_promises"]}
    assert {"D-009", "D-011"} <= decisions
    unassigned = [t for t in res.data["open_tickets"] if t["assignee"] == "unassigned"]
    assert any("PLAT-461" in t["ticket"] for t in unassigned)


def test_graph_is_not_decoration_ablation():
    """Remove the INTEGRATES_WITH relationships (keep every node and every text) in a copy:
    the same question can no longer be answered. The answer lives in the relationships."""
    try:
        db.graph("tallybird_ablation").delete()
    except Exception:
        pass
    db.graph(seed.config.SEED_GRAPH).copy("tallybird_ablation")
    db.run("MATCH ()-[r:INTEGRATES_WITH]->() DELETE r", graph_name="tallybird_ablation")
    full = db.run(Q.IMPACT_CUSTOMERS, {"id": "api:rest-v1"}, ro=True)
    ablated = db.run(Q.IMPACT_CUSTOMERS, {"id": "api:rest-v1"}, ro=True, graph_name="tallybird_ablation")
    assert len(full) == 3 and len(ablated) == 0
    texts = db.run("MATCH (m:Message) RETURN count(m) AS c", graph_name="tallybird_ablation")[0]["c"]
    assert texts == db.run("MATCH (m:Message) RETURN count(m) AS c")[0]["c"]


def test_org_xray_algorithms():
    x = xray.xray()
    assert len(x["communities"]) >= 2
    assert all(c["cross_team"] for c in x["communities"])
    assert {c["name"] for c in x["connectors"][:3]} & {"Sofia Martins", "Priya Raman", "Marco Rossi"}
    assert [d["name"] for d in x["key_docs"][:2]] == ["Webhook integration guide", "API Quickstart"]
    at_risk = {s["name"] for s in x["services"] if s["owner_left"]}
    assert at_risk == {"ledger-service", "auth-service"}
    assert {"ledger-service runbook", "auth-service runbook"} <= {d["name"] for d in x["orphaned_docs"]}


def test_read_only_queries_cannot_write():
    res = tools.graph_query(tools.Ctx(), "CREATE (:Person {name: 'Mallory'})")
    assert "error" in res.data
    with pytest.raises(Exception):
        db.run("MATCH (p:Person) SET p.name = 'x'", ro=True)
    assert not db.run("MATCH (p:Person {name: 'Mallory'}) RETURN p")


def test_approve_writes_tasks_and_reset_restores(fresh_graph):
    proposals = [{"title": "Update API Quickstart", "kind": "doc_fix", "priority": "normal",
                  "assignee": {"id": "person:kenji"}, "because": "Kenji wrote it", "targets": ["doc:api-quickstart"],
                  "draft": "- old\n  → new"}]
    out = ripple.approve("dec:D-011", proposals)
    assert out["created"] == 1
    rows = db.run("MATCH (t:Task)-[:FOR]->(:Decision {id: 'dec:D-011'}) MATCH (t)-[:ASSIGNED_TO]->(p:Person) RETURN p.name AS who")
    assert rows == [{"who": "Kenji Sato"}]
    work = tools.open_work(tools.Ctx(), "D-011")
    assert work.data["tasks"][0]["assignee"] == "Kenji Sato"
    seed.reset()
    assert not db.run("MATCH (t:Task) RETURN t")
