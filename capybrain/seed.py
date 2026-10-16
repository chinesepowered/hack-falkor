"""Build the Tallybird company graph in FalkorDB from the source files.

Usage:  python -m capybrain.seed          # build `<graph>_seed`, then copy it to the live graph
        python -m capybrain.seed --reset  # only restore the live graph from the seed copy

Everything here is deterministic and needs no LLM: structured exports (org chart, CRM,
tickets, PRs) are loaded as-is, free text is linked to entities with a gazetteer, docs are
split into claims, and every text gets a local embedding for the vector index.
"""
from __future__ import annotations

import argparse
import time
from collections import defaultdict
from itertools import combinations

from . import config, dataset, db, embeddings
from .linker import Linker

BATCH = 400


# --------------------------------------------------------------------------- helpers
def _chunks(rows: list, n: int = BATCH):
    for i in range(0, len(rows), n):
        yield rows[i:i + n]


class Writer:
    def __init__(self, graph_name: str):
        self.g = db.graph(graph_name)
        self.nodes = 0
        self.edges = 0
        self.known: set[str] = set()

    def nodes_(self, labels: str, rows: list[dict]) -> None:
        if not rows:
            return
        for chunk in _chunks(rows):
            props = [{k: v for k, v in r.items() if k != "embedding" and v is not None} for r in chunk]
            self.g.query(f"UNWIND $rows AS r CREATE (n:{labels}:Entity) SET n += r", {"rows": props})
            with_emb = [{"id": r["id"], "e": r["embedding"]} for r in chunk if r.get("embedding")]
            if with_emb:
                self.g.query("UNWIND $rows AS r MATCH (n:Entity {id: r.id}) SET n:Searchable, n.embedding = vecf32(r.e)",
                             {"rows": with_emb})
        self.nodes += len(rows)
        self.known.update(r["id"] for r in rows)

    def edges_(self, rel: str, rows: list[tuple], props: bool = False) -> None:
        """rows: (src_id, dst_id) or (src_id, dst_id, {props})."""
        clean, seen = [], set()
        for row in rows:
            src, dst = row[0], row[1]
            p = row[2] if len(row) > 2 else {}
            if src not in self.known or dst not in self.known or src == dst:
                continue
            key = (src, dst, tuple(sorted(p.items())))
            if key in seen:
                continue
            seen.add(key)
            clean.append({"s": src, "d": dst, "p": {k: v for k, v in p.items() if v is not None}})
        for chunk in _chunks(clean):
            q = f"UNWIND $rows AS r MATCH (a:Entity {{id: r.s}}), (b:Entity {{id: r.d}}) CREATE (a)-[e:{rel}]->(b)"
            if props:
                q += " SET e += r.p"
            self.g.query(q, {"rows": chunk})
        self.edges += len(clean)


def build_linker(ds: dataset.Dataset) -> Linker:
    lk = Linker()
    for p in ds.org["people"]:
        lk.add(p["id"], [p["name"], "@" + p["handle"]])
        lk.add(p["id"], [p["name"].split()[0]], case_sensitive=True)
    for s in ds.org["services"]:
        lk.add(s["id"], s.get("aliases", [s["name"]]))
    for a in ds.org["apis"]:
        lk.add(a["id"], a.get("aliases", [a["name"]]))
    for c in ds.org["customers"]:
        lk.add(c["id"], c.get("aliases", [c["name"]]))
    for d in ds.docs:
        lk.add(d.meta["id"], [d.meta["title"]] + dataset.DOC_ALIASES.get(d.meta["id"], []))
    for t in ds.tickets:
        lk.register(f"ticket:{t['key']}")
    for i in ds.org["incidents"]:
        lk.register(i["id"])
    for pr in ds.prs:
        lk.register(f"pr:{pr['number']}")
    return lk


def _short(text: str, n: int = 64) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


# --------------------------------------------------------------------------- schema
def create_schema(g) -> None:
    g.query("CREATE INDEX FOR (n:Entity) ON (n.id)")
    for label in ("Person", "Service", "Api", "Customer", "Decision", "Doc", "Claim", "Message", "Ticket", "Task"):
        g.query(f"CREATE INDEX FOR (n:{label}) ON (n.id)")
    g.query("CREATE INDEX FOR (n:Decision) ON (n.status)")
    g.query(f"CREATE VECTOR INDEX FOR (n:Searchable) ON (n.embedding) "
            f"OPTIONS {{dimension: {config.EMBED_DIM}, similarityFunction: 'cosine'}}")
    for label in ("Decision", "Claim", "Answer"):
        g.query(f"CREATE VECTOR INDEX FOR (n:{label}) ON (n.embedding) "
                f"OPTIONS {{dimension: {config.EMBED_DIM}, similarityFunction: 'cosine'}}")
    g.query("CALL db.idx.fulltext.createNodeIndex('Entity', 'name', 'aka')")


# --------------------------------------------------------------------------- build
def build(graph_name: str) -> dict:
    t0 = time.time()
    ds = dataset.load()
    lk = build_linker(ds)
    people = ds.people
    name_of = {p["id"]: p["name"] for p in ds.org["people"]}

    try:
        db.graph(graph_name).delete()
    except Exception:
        pass
    w = Writer(graph_name)
    create_schema(w.g)

    # ---- structured org data -------------------------------------------------
    org = ds.org
    w.nodes_("Team", [{"id": t["id"], "name": t["name"]} for t in org["teams"]])
    w.nodes_("Person", [{
        "id": p["id"], "name": p["name"], "handle": p["handle"], "title": p["title"],
        "status": p.get("status", "active"), "joined": p.get("joined"), "left": p.get("left"),
    } for p in org["people"]])
    w.g.query("MATCH (p:Person) WHERE p.status = 'active' SET p:Active")
    w.edges_("MEMBER_OF", [(p["id"], p["team"]) for p in org["people"]])
    w.edges_("REPORTS_TO", [(p["id"], p["manager"]) for p in org["people"] if p.get("manager")])

    w.nodes_("Api", [{"id": a["id"], "name": a["name"], "auth": a.get("auth"), "status": a.get("status"),
                      "aka": " | ".join(a.get("aliases", []))} for a in org["apis"]])
    w.nodes_("Service", [{"id": s["id"], "name": s["name"], "tier": s.get("tier"), "description": s.get("description"),
                          "aka": " | ".join(s.get("aliases", []))} for s in org["services"]])
    w.edges_("OWNS", [(s["team"], s["id"]) for s in org["services"]])
    w.edges_("OWNS", [(s["owner"], s["id"], {"since": people[s["owner"]].get("joined"), "until": s.get("owner_until")})
                      for s in org["services"] if s.get("owner")], props=True)
    w.edges_("DEPENDS_ON", [(s["id"], d) for s in org["services"] for d in s.get("depends_on", [])])
    w.edges_("EXPOSES", [(s["id"], a) for s in org["services"] for a in s.get("exposes", [])])
    w.edges_("CALLS", [(s["id"], a) for s in org["services"] for a in s.get("calls", [])])
    w.edges_("AUTHENTICATES", [(s["id"], a) for s in org["services"] for a in s.get("authenticates", [])])

    w.nodes_("Customer", [{"id": c["id"], "name": c["name"], "arr": c["arr"], "tier": c["tier"],
                           "aka": " | ".join(c.get("aliases", []))} for c in org["customers"]])
    w.edges_("INTEGRATES_WITH", [(c["id"], a) for c in org["customers"] for a in c.get("integrates", [])])
    w.edges_("ACCOUNT_MANAGER_OF", [(c["account_manager"], c["id"]) for c in org["customers"]])
    w.nodes_("Channel", [{"id": c["id"], "name": "#" + c["name"]} for c in org["channels"]])

    # ---- texts that get embeddings --------------------------------------------
    texts: dict[str, str] = {}

    incidents = org["incidents"]
    for i in incidents:
        texts[i["id"]] = f"{i['key']} {i['title']}. {i['summary']}"
    meetings = ds.meetings
    for m in meetings:
        texts[m.meta["id"]] = f"{m.meta['title']} ({m.meta['date']})\n{m.body[:1500]}"
    docs = ds.docs
    claims = []
    for d in docs:
        texts[d.meta["id"]] = f"{d.meta['title']}\n{d.body[:1500]}"
        for n, sentence in enumerate(dataset.split_claims(d.body), start=1):
            cid = f"claim:{d.meta['id'].split(':', 1)[1]}-{n:02d}"
            claims.append({"id": cid, "doc": d.meta["id"], "text": sentence, "ord": n, "at": d.meta["updated"]})
            texts[cid] = f"{d.meta['title']}: {sentence}"
    decisions = []
    for src in docs + meetings:
        dec = src.meta.get("decision")
        if dec:
            decisions.append({**dec, "_source": src.meta["id"]})
            texts[dec["id"]] = f"{dec['title']}. {dec['summary']}"
    chan_name = {c["id"]: c["name"] for c in org["channels"]}
    for m in ds.messages:
        texts[m["id"]] = f"#{chan_name[m['channel']]} {name_of[m['author']]}: {m['text']}"
    for t in ds.tickets:
        texts[f"ticket:{t['key']}"] = f"{t['key']} {t['title']}. {t.get('description', '')}"
    for pr in ds.prs:
        texts[f"pr:{pr['number']}"] = f"PR #{pr['number']} {pr['title']}. {pr.get('body', '')}"

    ids = list(texts)
    vecs = dict(zip(ids, embeddings.embed_many([texts[i] for i in ids])))

    # ---- incidents, meetings, docs, claims ------------------------------------
    w.nodes_("Incident", [{"id": i["id"], "key": i["key"], "name": f"{i['key']} {i['title']}", "title": i["title"],
                           "severity": i["severity"], "at": i["date"], "text": i["summary"],
                           "embedding": vecs[i["id"]]} for i in incidents])
    w.edges_("AFFECTED", [(i["id"], s) for i in incidents for s in i.get("affected", [])])
    w.edges_("IMPACTED", [(i["id"], c) for i in incidents for c in i.get("customers", [])])
    w.edges_("RESOLVED", [(i["resolved_by"], i["id"]) for i in incidents if i.get("resolved_by")])

    w.nodes_("Meeting", [{"id": m.meta["id"], "name": f"{m.meta['title']} ({m.meta['date']})", "title": m.meta["title"],
                          "at": m.meta["date"], "text": m.body, "path": m.path,
                          "embedding": vecs[m.meta["id"]]} for m in meetings])
    w.edges_("ATTENDED", [(p, m.meta["id"]) for m in meetings for p in m.meta.get("attendees", [])])

    w.nodes_("Doc", [{"id": d.meta["id"], "name": d.meta["title"], "title": d.meta["title"], "kind": d.meta["kind"],
                      "updated": d.meta["updated"], "at": d.meta["updated"], "text": d.body, "path": d.path,
                      "status": "current", "embedding": vecs[d.meta["id"]]} for d in docs])
    w.edges_("AUTHORED", [(a, d.meta["id"]) for d in docs for a in d.meta.get("authors", [])])
    w.edges_("CITES", [(d.meta["id"], c) for d in docs for c in d.meta.get("cites", [])])

    w.nodes_("Claim", [{"id": c["id"], "name": _short(c["text"], 60), "text": c["text"], "doc": c["doc"], "ord": c["ord"], "at": c["at"],
                        "status": "current", "embedding": vecs[c["id"]]} for c in claims])
    w.edges_("STATES", [(c["doc"], c["id"]) for c in claims])

    # ---- messages, tickets, PRs --------------------------------------------------
    w.nodes_("Message", [{"id": m["id"], "name": f"{name_of[m['author']].split()[0]} in #{chan_name[m['channel']]}: {_short(m['text'], 48)}",
                          "text": m["text"], "ts": m["ts"], "at": m["ts"][:10], "channel": "#" + chan_name[m["channel"]],
                          "embedding": vecs[m["id"]]} for m in ds.messages])
    w.edges_("POSTED", [(m["author"], m["id"]) for m in ds.messages])
    w.edges_("IN", [(m["id"], m["channel"]) for m in ds.messages])
    w.edges_("REPLY_TO", [(m["id"], m["reply_to"]) for m in ds.messages if m.get("reply_to")])

    w.nodes_("Ticket", [{"id": f"ticket:{t['key']}", "key": t["key"], "name": f"{t['key']} {t['title']}", "title": t["title"],
                         "text": t.get("description", ""), "status": t["status"], "priority": t.get("priority"),
                         "created": t["created"], "resolved": t.get("resolved"), "at": t["created"],
                         "embedding": vecs[f"ticket:{t['key']}"]} for t in ds.tickets])
    w.edges_("REPORTED", [(t["reporter"], f"ticket:{t['key']}") for t in ds.tickets if t.get("reporter")])
    w.edges_("ASSIGNED_TO", [(f"ticket:{t['key']}", t["assignee"]) for t in ds.tickets if t.get("assignee")])
    w.edges_("ABOUT", [(f"ticket:{t['key']}", s) for t in ds.tickets for s in t.get("services", [])])
    w.edges_("FOR_CUSTOMER", [(f"ticket:{t['key']}", c) for t in ds.tickets for c in t.get("customers", [])])
    w.edges_("PART_OF", [(f"ticket:{t['key']}", t["incident"]) for t in ds.tickets if t.get("incident")])

    w.nodes_("PR", [{"id": f"pr:{p['number']}", "number": p["number"], "repo": p["repo"],
                     "name": f"PR #{p['number']} {p['title']}", "title": p["title"], "text": p.get("body", ""),
                     "state": p.get("state", "merged"), "merged": p.get("merged"), "at": p.get("merged") or config.TODAY,
                     "embedding": vecs[f"pr:{p['number']}"]} for p in ds.prs])
    w.edges_("AUTHORED", [(p["author"], f"pr:{p['number']}") for p in ds.prs])
    w.edges_("REVIEWED", [(r, f"pr:{p['number']}") for p in ds.prs for r in p.get("reviewers", [])])
    w.edges_("TOUCHES", [(f"pr:{p['number']}", s) for p in ds.prs for s in p.get("services", [])])
    w.edges_("FIXES", [(f"pr:{p['number']}", f"ticket:{k}") for p in ds.prs for k in p.get("fixes", [])])

    # ---- decisions (from ADR and meeting front matter) ---------------------------
    w.nodes_("Decision", [{"id": d["id"], "name": f"{d['id'].split(':')[1]}: {d['title']}", "title": d["title"],
                           "summary": d["summary"], "text": d["summary"], "at": d["date"], "status": "active",
                           "embedding": vecs[d["id"]]} for d in decisions])
    w.edges_("DOCUMENTED_IN", [(d["id"], d["_source"]) for d in decisions if d["_source"].startswith("doc:")])
    w.edges_("DECIDED_IN", [(d["id"], d["meeting"]) for d in decisions if d.get("meeting")])
    w.edges_("DECIDED_IN", [(d["id"], d["_source"]) for d in decisions if d["_source"].startswith("mtg:")])
    w.edges_("DECIDED", [(p, d["id"]) for d in decisions for p in d.get("deciders", [])])
    w.edges_("TRIGGERED_BY", [(d["id"], d["triggered_by"]) for d in decisions if d.get("triggered_by")])
    w.edges_("AFFECTS", [(d["id"], a) for d in decisions for a in d.get("affects", [])])
    w.edges_("IMPLEMENTED_BY", [(d["id"], p) for d in decisions for p in d.get("implemented_by", [])])
    w.edges_("EVIDENCED_BY", [(d["id"], m) for d in decisions for m in d.get("evidence", [])])
    alts = []
    for d in decisions:
        for n, alt in enumerate(d.get("rejected", []), start=1):
            alts.append({"id": f"alt:{d['id'].split(':')[1]}-{n}", "name": alt["option"], "option": alt["option"],
                         "reason": alt["reason"], "decision": d["id"]})
    w.nodes_("Alternative", alts)
    w.edges_("REJECTED", [(a["decision"], a["id"]) for a in alts])

    # ---- entity links from free text (gazetteer) -------------------------------------
    mentions, about = [], []
    for m in ds.messages:
        mentions += [(m["id"], e) for e in lk.link(m["text"], exclude={m["author"]})]
    for t in ds.tickets:
        mentions += [(f"ticket:{t['key']}", e) for e in lk.link(f"{t['title']}. {t.get('description', '')}",
                                                               exclude={f"ticket:{t['key']}"})]
    for p in ds.prs:
        mentions += [(f"pr:{p['number']}", e) for e in lk.link(f"{p['title']}. {p.get('body', '')}",
                                                              exclude={f"pr:{p['number']}"})]
    for m in meetings:
        mentions += [(m.meta["id"], e) for e in lk.link(m.body)]
        about += [(m.meta["id"], e) for e in m.meta.get("about", [])]
    for d in docs:
        about += [(d.meta["id"], e) for e in d.meta.get("about", [])]
        mentions += [(d.meta["id"], e) for e in lk.link(d.body, exclude={d.meta["id"]})]
    claim_about = []
    for c in claims:
        claim_about += [(c["id"], e) for e in lk.link(c["text"], exclude={c["doc"]})]
    w.edges_("MENTIONS", mentions)
    w.edges_("ABOUT", about)
    w.edges_("ABOUT", claim_about)

    # ---- derived collaboration graph (computed with Cypher over the graph above) -----
    collab_queries = {
        "code review": ("MATCH (a:Person)-[:AUTHORED]->(:PR)<-[:REVIEWED]-(b:Person) RETURN a.id AS a, b.id AS b", 2.0),
        "thread reply": ("MATCH (a:Person)-[:POSTED]->(:Message)-[:REPLY_TO]->(:Message)<-[:POSTED]-(b:Person) RETURN a.id AS a, b.id AS b", 1.0),
        "same thread": ("MATCH (a:Person)-[:POSTED]->(:Message)-[:REPLY_TO]->(root:Message)<-[:REPLY_TO]-(:Message)<-[:POSTED]-(b:Person) RETURN a.id AS a, b.id AS b", 0.5),
        "meeting": ("MATCH (a:Person)-[:ATTENDED]->(:Meeting)<-[:ATTENDED]-(b:Person) RETURN a.id AS a, b.id AS b", 1.0),
        "ticket": ("MATCH (a:Person)-[:REPORTED]->(:Ticket)-[:ASSIGNED_TO]->(b:Person) RETURN a.id AS a, b.id AS b", 1.0),
        "decision": ("MATCH (a:Person)-[:DECIDED]->(:Decision)<-[:DECIDED]-(b:Person) RETURN a.id AS a, b.id AS b", 1.0),
    }
    weight: dict[tuple[str, str], float] = defaultdict(float)
    why: dict[tuple[str, str], set] = defaultdict(set)
    for label, (q, wgt) in collab_queries.items():
        for row in w.g.query(q).result_set:
            a, b = row
            if a == b:
                continue
            key = tuple(sorted((a, b)))
            weight[key] += wgt / 2 if label in ("meeting", "decision", "same thread") else wgt
            why[key].add(label)
    # Keep ties with weight >= 2.5 (e.g. a code review plus a shared thread or meeting) and store
    # them in both directions so the algorithms treat the collaboration graph as undirected.
    ties = [(a, b, {"weight": round(v, 2), "via": ", ".join(sorted(why[(a, b)]))})
            for (a, b), v in weight.items() if v >= 2.5]
    w.edges_("COLLABORATES", ties + [(b, a, p) for a, b, p in ties], props=True)

    stats = {"nodes": w.nodes, "edges": w.edges, "seconds": round(time.time() - t0, 1)}
    return stats


def reset() -> None:
    """Restore the live graph from the pristine seed copy (FalkorDB GRAPH.COPY)."""
    try:
        db.graph(config.GRAPH).delete()
    except Exception:
        pass
    db.graph(config.SEED_GRAPH).copy(config.GRAPH)


def wait_for_db(timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while True:
        try:
            db.client().list_graphs()
            return
        except Exception:
            if time.time() > deadline:
                raise
            time.sleep(2)


def ensure_seeded() -> None:
    wait_for_db()
    names = set(db.client().list_graphs())
    if config.SEED_GRAPH not in names:
        build(config.SEED_GRAPH)
    if config.GRAPH not in names:
        reset()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="only copy the seed graph over the live graph")
    args = ap.parse_args()
    if not args.reset:
        print("building", config.SEED_GRAPH, build(config.SEED_GRAPH))
    reset()
    counts = db.run("MATCH (n) RETURN labels(n) AS labels, count(*) AS c ORDER BY c DESC")
    print("live graph", config.GRAPH, {"/".join(l for l in r["labels"] if l not in db.INTERNAL_LABELS): r["c"] for r in counts})


if __name__ == "__main__":
    main()
