"""Render the Cypher catalog (capybrain/queries.py) into docs/queries.md."""
from pathlib import Path

from capybrain.queries import Q

ROOT = Path(__file__).resolve().parents[1]

SECTIONS = [
    ("Retrieval: finding where to start", ["vector_search", "decision_search", "claim_search", "answer_search", "fulltext_search", "node_by_id", "neighbours", "thread"]),
    ("Decisions: tracing why", ["decision_trace", "evidence_authors", "incident_thread"]),
    ("People: who owns and who knows", ["expertise", "expertise_evidence", "owners"]),
    ("Impact: what a change touches", ["impact_services", "impact_customers", "impact_claims", "impact_decisions", "impact_tickets"]),
    ("Work: follow-up tasks", ["open_tasks", "decisions_with_tasks"]),
    ("Org X-ray: graph algorithms", ["communities", "connectors", "key_docs", "bus_factor", "orphaned_docs"]),
    ("Views", ["overview_nodes", "overview_edges", "stats"]),
]


def main() -> None:
    out = ["# Cypher catalog", "",
           "Every graph query CapyBrain runs, generated from [`capybrain/queries.py`](../capybrain/queries.py) "
           "by `python -m scripts.export_queries`. Writes (seeding, the ripple pipeline, approving tasks) live in "
           "[`seed.py`](../capybrain/seed.py) and [`ripple.py`](../capybrain/ripple.py); the agent's own Cypher "
           "(`graph_query` tool) runs through `GRAPH.RO_QUERY`, so the database refuses any write.", ""]
    listed = set()
    for title, names in SECTIONS:
        out += [f"## {title}", ""]
        for name in names:
            listed.add(name)
            out += [f"### `{name}`", "", Q[name]["purpose"], "", "```cypher", Q[name]["cypher"], "```", ""]
    missing = [n for n in Q if n not in listed]
    if missing:
        out += ["## Other", ""]
        for name in missing:
            out += [f"### `{name}`", "", Q[name]["purpose"], "", "```cypher", Q[name]["cypher"], "```", ""]
    (ROOT / "docs").mkdir(exist_ok=True)
    (ROOT / "docs" / "queries.md").write_text("\n".join(out))
    print(f"wrote docs/queries.md with {len(Q)} queries")


if __name__ == "__main__":
    main()
