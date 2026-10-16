"""Org X-ray: graph algorithms over the company graph (label propagation, betweenness, PageRank)
plus knowledge-concentration queries. Every insight carries the Cypher that produced it."""
from __future__ import annotations

from collections import Counter

from . import db
from . import queries as Q


def _rows(name: str, **params) -> list[dict]:
    return db.to_json(db.run(Q.Q[name]["cypher"], params, ro=True))


def xray() -> dict:
    communities = []
    for i, r in enumerate(_rows("communities")):
        teams = Counter(m["team"] for m in r["members"])
        if len(r["members"]) < 2:
            continue
        communities.append({"community": i, "size": len(r["members"]), "members": r["members"],
                            "teams": dict(teams.most_common()), "cross_team": len(teams) > 1})

    connectors = [{"id": r["node"]["id"], "name": r["node"]["name"], "title": r["node"].get("title"),
                   "team": r["team"], "score": round(r["score"], 1)} for r in _rows("connectors", limit=6)]

    key_docs = [{"id": r["node"]["id"], "name": r["node"]["name"], "status": r["node"].get("status", "current"),
                 "updated": r["node"].get("updated"), "score": round(r["score"], 4)} for r in _rows("key_docs", limit=6)]

    services = []
    for r in _rows("bus_factor"):
        people = [p for p in r["people"] if p]
        total = sum(p["n"] for p in people) or 0
        gone = sum(p["n"] for p in people if p["status"] == "departed")
        active = sorted([p for p in people if p["status"] != "departed"], key=lambda p: -p["n"])
        owner = r.get("owner")
        services.append({
            "id": r["s"]["id"], "name": r["s"]["name"], "tier": r["s"].get("tier"),
            "owner": owner["name"] if owner else None,
            "owner_left": bool(owner and owner.get("status") == "departed"),
            "changes": total, "share_by_departed": round(gone / total, 2) if total else 0.0,
            "active_people": len(active), "top_active": [p["name"] for p in active[:3]],
        })
    services.sort(key=lambda s: (not s["owner_left"], -s["share_by_departed"], s["active_people"]))

    orphaned = [{"id": r["d"]["id"], "name": r["d"]["name"], "authors": [a["name"] for a in r["authors"]],
                 "updated": r["d"].get("updated")} for r in _rows("orphaned_docs")]

    return {
        "communities": communities, "connectors": connectors, "key_docs": key_docs,
        "services": services, "orphaned_docs": orphaned,
        "cypher": {k: Q.Q[k]["cypher"] for k in ("communities", "connectors", "key_docs", "bus_factor", "orphaned_docs")},
    }
