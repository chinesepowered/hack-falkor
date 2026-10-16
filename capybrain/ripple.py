"""Ripple: a change lands, the brain updates itself, finds what went stale, and drafts the follow-up work.

ingest() is a generator of events for the UI:
  message    the new message is written to the graph and linked to what it mentions
  extracted  the LLM reads it: is it a decision? what does it affect?
  decision   a Decision node is created with its evidence, deciders and AFFECTS links
  impact     multi-hop traversal from the affected entities, grouped in rings (hops)
  conflicts  earlier decisions it supersedes, updates or contradicts (LLM judge over graph candidates)
  stale      doc statements the decision contradicts (LLM judge over graph + vector candidates)
  proposals  follow-up tasks, each assigned through the ownership graph with a reason
  done
"""
from __future__ import annotations

import json
import re
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from . import config, db, embeddings, llm, tools
from . import queries as Q
from .tools import Ctx, ToolResult, resolve, slim, snippet

EXTRACT_SYSTEM = """You turn one workplace chat message into structured data for a company knowledge graph.
Return JSON only:
{"is_decision": true|false,
 "title": "short imperative title of the decision or change (max 12 words)",
 "summary": "one or two sentences: what changes, from when, for whom",
 "effective_date": "YYYY-MM-DD or null",
 "affects": ["names of the APIs, services, customers or teams that change, break or stop working because of this decision, using the exact names from the known entities list. Do NOT list replacements or migration targets: if v1 is switched off in favour of v2, only v1 is affected."]}
A message is a decision if it announces something the company will do or stop doing (a policy, a date, an architecture or ownership change). Questions and chatter are not decisions."""

CONFLICT_SYSTEM = """You compare a NEW company decision with EARLIER decisions and promises from the company graph.
For each earlier decision choose one relation:
- "supersedes": the new decision replaces it entirely; it no longer holds.
- "updates": the new decision changes part of it (for example sets a date it left open); the rest still holds.
- "conflicts": both cannot be true at the same time, e.g. it breaks a promise made to a customer; a human must resolve it.
- "consistent": no tension.
Return JSON only: {"relations": [{"id": "...", "relation": "...", "reason": "one short sentence"}]}"""

STALE_SYSTEM = """You check documentation against a NEW company decision.
For each statement from a doc, decide whether the decision makes it wrong or outdated.
Mark a statement only if a reader following it after the decision would be misled. Statements about unrelated things are "ok".
Return JSON only, listing ONLY the statements that are not ok:
{"stale": [{"id": "...", "verdict": "contradicted" | "outdated", "why": "short reason (max 15 words)", "rewrite": "the corrected statement, same length as the original"}]}"""

NOTICE_SYSTEM = """You draft short, friendly customer emails from an account manager about a platform change.
Each email: a subject line and a body of at most 90 words, specific to that customer, with the deadline and a concrete next step.
If the change conflicts with a commitment made to the customer, do NOT draft an email: set "hold": true and explain why in "reason".
Return JSON only: {"emails": [{"customer": "...", "hold": false, "subject": "...", "body": "..."}]}"""


def _ev(kind: str, **data) -> dict:
    return {"type": kind, **data}


def _next_decision_id() -> str:
    rows = db.run("MATCH (d:Decision) RETURN d.id AS id")
    nums = [int(m.group(1)) for r in rows if (m := re.search(r"D-(\d+)", r["id"]))]
    return f"dec:D-{(max(nums) + 1 if nums else 1):03d}"


def _person(pid: str) -> dict | None:
    return tools.by_id(pid)


def _successor(ctx: Ctx, subject_id: str) -> tuple[dict | None, str]:
    """Best active person for something whose owner left, using the expertise query."""
    rows = db.to_json(db.run(Q.EXPERTISE, {"id": subject_id, "limit": 8}, ro=True))
    for r in rows:
        if r["p"].get("status") != "departed":
            sig = {k: r[k] for k in ("authored", "reviewed", "discussed", "docs", "meetings") if r[k]}
            why = ", ".join(f"{v} {k}" for k, v in sig.items())
            return r["p"], why
    return None, ""


# --------------------------------------------------------------------------- pipeline
def ingest(text: str, author_id: str, channel_id: str, ts: str | None = None) -> Iterator[dict]:
    t0 = time.time()
    ctx = Ctx()
    ts = ts or f"{config.TODAY}T09:30:00Z"
    author = _person(author_id)
    if not author:
        yield _ev("error", message=f"unknown author {author_id}")
        return

    # 1. the message itself -------------------------------------------------------
    mid = f"msg:live-{uuid.uuid4().hex[:8]}"
    chan = db.run("MATCH (c:Channel {id: $id}) RETURN c.name AS name", {"id": channel_id})
    chan_name = chan[0]["name"] if chan else "#general"
    mentions = tools.linker().link(text, exclude={author_id})
    db.run("CREATE (m:Message:Entity:Searchable {id: $id, name: $name, text: $text, ts: $ts, at: $at, channel: $ch}) "
           "SET m.embedding = vecf32($vec)",
           {"id": mid, "name": f"{author['name'].split()[0]} in {chan_name}: {text[:48]}…", "text": text, "ts": ts,
            "at": ts[:10], "ch": chan_name, "vec": embeddings.embed(f"{chan_name} {author['name']}: {text}")})
    db.run("MATCH (p:Entity {id: $a}), (m:Entity {id: $m}), (c:Entity {id: $c}) CREATE (p)-[:POSTED]->(m), (m)-[:IN]->(c)",
           {"a": author_id, "m": mid, "c": channel_id})
    if mentions:
        db.run("MATCH (m:Entity {id: $m}) UNWIND $ids AS x MATCH (e:Entity {id: x}) CREATE (m)-[:MENTIONS]->(e)",
               {"m": mid, "ids": mentions})
    msg = tools.by_id(mid)
    yield _ev("message", node=slim(msg), author=slim(author), mentions=mentions,
              nodes=[slim(msg), slim(author)] + [slim(n) for n in map(tools.by_id, mentions) if n],
              links=[{"source": author_id, "type": "POSTED", "target": mid}] +
                    [{"source": mid, "type": "MENTIONS", "target": e} for e in mentions])

    # 2. extraction ----------------------------------------------------------------
    known = db.run("MATCH (n:Entity) WHERE n:Api OR n:Service OR n:Customer OR n:Team RETURN n.name AS name")
    user = (f"Message from {author['name']} ({author.get('title')}) in {chan_name} on {ts[:10]}:\n\"{text}\"\n\n"
            f"Known entities: {', '.join(r['name'] for r in known)}\n"
            f"Entities detected by the gazetteer: {', '.join(mentions) or 'none'}")
    try:
        ext = llm.complete_json(EXTRACT_SYSTEM, user, max_tokens=700)
    except Exception as e:  # noqa: BLE001
        yield _ev("error", message=f"extraction failed: {e}")
        return
    if not ext.get("is_decision"):
        yield _ev("extracted", extraction=ext, affects=[])
        yield _ev("done", decision_id=None, seconds=round(time.time() - t0, 1),
                  note="Not a decision; stored as a message and linked to what it mentions.")
        return
    affects: list[dict] = []
    for name in ext.get("affects", []) or []:
        n = resolve(name, prefer=("Api", "Service", "Customer", "Team"))
        if n and n["type"] in ("Api", "Service", "Customer", "Team") and n["id"] not in {a["id"] for a in affects}:
            affects.append(n)
    if not affects:  # fall back to what the gazetteer saw
        affects = [n for n in (tools.by_id(e) for e in mentions if e.split(":")[0] in ("api", "svc")) if n]
    yield _ev("extracted", extraction=ext, affects=[slim(a) for a in affects])

    # 3. the decision node -------------------------------------------------------------
    did = _next_decision_id()
    title = ext.get("title") or text[:80]
    summary = ext.get("summary") or text
    db.run("CREATE (d:Decision:Entity:Searchable {id: $id, name: $name, title: $title, summary: $summary, text: $summary, "
           "at: $at, effective: $eff, status: 'active', source: 'chat'}) SET d.embedding = vecf32($vec)",
           {"id": did, "name": f"{did.split(':')[1]}: {title}", "title": title, "summary": summary, "at": ts[:10],
            "eff": ext.get("effective_date"), "vec": embeddings.embed(f"{title}. {summary}")})
    db.run("MATCH (d:Entity {id: $d}), (m:Entity {id: $m}), (p:Entity {id: $p}) "
           "CREATE (d)-[:EVIDENCED_BY]->(m), (p)-[:DECIDED]->(d)", {"d": did, "m": mid, "p": author_id})
    db.run("MATCH (d:Entity {id: $d}) UNWIND $ids AS x MATCH (e:Entity {id: x}) CREATE (d)-[:AFFECTS]->(e)",
           {"d": did, "ids": [a["id"] for a in affects]})
    decision = tools.by_id(did)
    yield _ev("decision", node=slim(decision),
              nodes=[slim(decision)] + [slim(a) for a in affects],
              links=[{"source": did, "type": "EVIDENCED_BY", "target": mid},
                     {"source": author_id, "type": "DECIDED", "target": did}] +
                    [{"source": did, "type": "AFFECTS", "target": a["id"]} for a in affects])

    # 4. impact (pure graph, instant) ---------------------------------------------------
    rings: dict[int, dict] = {1: {}, 2: {}, 3: {}}
    ring_links: list[dict] = []
    impact = {"services": [], "customers": [], "decisions": [], "tickets": []}
    for a in affects:
        rings[1][a["id"]] = slim(a)
        r = tools.impact_of(ctx, a["id"])
        for n in r.nodes.values():
            if n["id"] == a["id"]:
                continue
            hop = 3 if n["type"] in ("Person", "Team", "Ticket") else 2
            if n["id"] not in rings[1] and n["id"] not in rings[2]:
                rings[hop].setdefault(n["id"], n)
        ring_links += r.links
        impact["services"] += r.data.get("services", [])
        impact["customers"] += r.data.get("customers", [])
        impact["decisions"] += [d for d in r.data.get("decisions_and_promises", []) if not d["decision"].startswith(did.split(":")[1])]
        impact["tickets"] += r.data.get("open_tickets", [])
    yield _ev("impact", rings=[{"hop": h, "nodes": list(v.values())} for h, v in rings.items()], links=ring_links,
              counts={k: len(v) for k, v in impact.items()})

    # 5-7. LLM judges run in parallel ------------------------------------------------------
    affect_ids = [a["id"] for a in affects]
    cand = db.to_json(db.run(
        "MATCH (old:Decision)-[:AFFECTS]->(x:Entity) WHERE x.id IN $ids AND old.id <> $d AND old.status = 'active' "
        "OPTIONAL MATCH (p:Person)-[:DECIDED]->(old) RETURN DISTINCT old, collect(DISTINCT p.name) AS by",
        {"ids": affect_ids, "d": did}))
    claim_rows = []
    for a in affects:
        claim_rows += db.to_json(db.run(Q.IMPACT_CLAIMS, {"id": a["id"]}, ro=True))
    vec_claims = db.to_json(db.run(Q.CLAIM_SEARCH, {"k": 12, "vec": embeddings.embed(f"{title}. {summary}")}, ro=True))
    claims: dict[str, dict] = {}
    historical = ("adr", "postmortem", "okrs", "onepager")  # records of the past: superseded, not edited
    for r in claim_rows:
        if r["d"].get("kind") not in historical:
            claims.setdefault(r["cl"]["id"], {"claim": r["cl"], "doc": r["d"]})
    for r in vec_claims:
        if r["score"] < 0.35 and r["d"].get("kind") not in historical:
            claims.setdefault(r["node"]["id"], {"claim": r["node"], "doc": r["d"]})
    customers = {c["customer"]: c for c in impact["customers"]}

    def judge_conflicts():
        if not cand:
            return {"relations": []}
        listing = "\n".join(f"- id={r['old']['id']} ({r['old'].get('at')}, by {', '.join(r['by'])}): "
                            f"{r['old']['title']}. {r['old'].get('summary', '')}" for r in cand)
        return llm.complete_json(CONFLICT_SYSTEM, f"NEW decision ({ts[:10]}): {title}. {summary}\n\nEARLIER:\n{listing}",
                                 max_tokens=4000, think=True)

    def judge_batch(batch):
        listing = "\n".join(f"- id={c['claim']['id']} [{c['doc']['title']}]: {c['claim']['text']}" for c in batch)
        try:
            return llm.complete_json(STALE_SYSTEM, f"NEW decision ({ts[:10]}): {title}. {summary}\n\nSTATEMENTS:\n{listing}",
                                     max_tokens=1200).get("stale", [])
        except Exception:  # noqa: BLE001
            return []

    def judge_claims():
        items = list(claims.values())
        batches = [items[i:i + 5] for i in range(0, len(items), 5)]
        with ThreadPoolExecutor(max_workers=6) as inner:
            return {"stale": [s for part in inner.map(judge_batch, batches) for s in part]}

    def draft_notices():
        if not customers:
            return {"emails": []}
        promises = [d for d in impact["decisions"]]
        listing = "\n".join(f"- {c['customer']} (account manager {c['account_manager']}, integrates via {c['via_api']})"
                            for c in customers.values())
        prom = "\n".join(f"- {p['decision']} ({p['date']}): {p.get('summary', '')}" for p in promises) or "none"
        return llm.complete_json(NOTICE_SYSTEM, f"Change: {title}. {summary}\n\nCustomers:\n{listing}\n\n"
                                                f"Existing commitments and decisions:\n{prom}", max_tokens=1500)

    with ThreadPoolExecutor(max_workers=3) as pool:
        f_conf, f_stale, f_mail = pool.submit(judge_conflicts), pool.submit(judge_claims), pool.submit(draft_notices)

        # conflicts
        try:
            relations = f_conf.result().get("relations", [])
        except Exception as e:  # noqa: BLE001
            relations, _ = [], e
        by_old = {r["old"]["id"]: r for r in cand}
        conflict_items, conflict_links, conflict_nodes = [], [], []
        for rel in relations:
            rid = str(rel.get("id", "")).strip()
            old = by_old.get(rid) or by_old.get(f"dec:{rid}")
            kind = (rel.get("relation") or "").lower()
            if not old or kind not in ("supersedes", "updates", "conflicts"):
                continue
            edge = {"supersedes": "SUPERSEDES", "updates": "UPDATES", "conflicts": "CONFLICTS_WITH"}[kind]
            db.run(f"MATCH (n:Entity {{id: $n}}), (o:Entity {{id: $o}}) CREATE (n)-[:{edge} {{reason: $why}}]->(o)",
                   {"n": did, "o": old["old"]["id"], "why": rel.get("reason", "")})
            if kind == "supersedes":
                db.run("MATCH (o:Decision {id: $o}) SET o.status = 'superseded'", {"o": old["old"]["id"]})
            conflict_items.append({"id": old["old"]["id"], "decision": old["old"]["name"], "relation": kind,
                                   "reason": rel.get("reason", ""), "by": old["by"],
                                   "cite": ctx.cites.add(old["old"])})
            conflict_nodes.append(slim(old["old"]))
            conflict_links.append({"source": did, "type": edge, "target": old["old"]["id"]})
        yield _ev("conflicts", items=conflict_items, nodes=conflict_nodes, links=conflict_links)

        # stale docs
        try:
            stale = f_stale.result().get("stale", [])
        except Exception:  # noqa: BLE001
            stale = []
        stale_docs: dict[str, dict] = {}
        stale_links = []
        for s in stale:
            c = claims.get(s.get("id"))
            if not c:
                continue
            doc = c["doc"]
            db.run("MATCH (cl:Claim {id: $c}), (d:Entity {id: $d}) SET cl.status = 'stale', cl.stale_why = $why, "
                   "cl.rewrite = $rw CREATE (cl)-[:CONTRADICTED_BY]->(d)",
                   {"c": c["claim"]["id"], "d": did, "why": s.get("why", ""), "rw": s.get("rewrite", "")})
            db.run("MATCH (doc:Doc {id: $id}) SET doc.status = 'stale', doc.stale_since = $at", {"id": doc["id"], "at": ts[:10]})
            entry = stale_docs.setdefault(doc["id"], {"doc": slim({**doc, "status": "stale"}), "claims": []})
            entry["claims"].append({"id": c["claim"]["id"], "text": c["claim"]["text"], "verdict": s.get("verdict"),
                                    "why": s.get("why"), "rewrite": s.get("rewrite")})
            stale_links.append({"source": doc["id"], "type": "CONTRADICTED_BY", "target": did})
        yield _ev("stale", docs=list(stale_docs.values()), checked=len(claims),
                  nodes=[d["doc"] for d in stale_docs.values()], links=stale_links)

        try:
            emails = {e.get("customer"): e for e in f_mail.result().get("emails", [])}
        except Exception:  # noqa: BLE001
            emails = {}

    # 8. proposals ---------------------------------------------------------------------
    proposals = []

    def propose(kind, title_, assignee, because, targets, draft=None, priority="normal"):
        proposals.append({"pid": f"p{len(proposals) + 1}", "kind": kind, "title": title_, "priority": priority,
                          "assignee": slim(assignee) if assignee else None, "because": because,
                          "targets": targets, "draft": draft})

    conflict_with = {c["id"]: c for c in conflict_items if c["relation"] == "conflicts"}
    for cid, c in conflict_with.items():
        deciders = db.to_json(db.run("MATCH (p:Person)-[:DECIDED]->(:Decision {id: $id}) WHERE p.status = 'active' "
                                     "AND p.id <> $author RETURN p ORDER BY p.name", {"id": cid, "author": author_id}))
        owner = deciders[0]["p"] if deciders else author
        affected_customers = db.to_json(db.run("MATCH (:Decision {id: $id})-[:AFFECTS]->(c:Customer) RETURN c", {"id": cid}))
        propose("resolve_conflict", f"Resolve conflict: {c['decision']}", owner,
                f"{c['reason']} {owner['name']} made that commitment ({c['decision'].split(':')[0]}).",
                [cid] + [r["c"]["id"] for r in affected_customers], priority="high")

    for d in stale_docs.values():
        doc = d["doc"]
        authors = db.to_json(db.run("MATCH (p:Person)-[:AUTHORED]->(:Doc {id: $id}) RETURN p", {"id": doc["id"]}))
        active = [a["p"] for a in authors if a["p"].get("status") != "departed"]
        if active:
            who, why = active[0], f"{active[0]['name']} wrote this doc."
        else:
            about = db.to_json(db.run("MATCH (:Doc {id: $id})-[:ABOUT]->(x) WHERE x:Service OR x:Api RETURN x LIMIT 1",
                                      {"id": doc["id"]}))
            who, sig = _successor(ctx, about[0]["x"]["id"]) if about else (author, "")
            gone = ", ".join(a["p"]["name"] for a in authors)
            why = f"Its author {gone} has left; {who['name'] if who else 'nobody'} knows {about[0]['x']['name'] if about else 'the area'} best ({sig})."
        fixes = "\n".join(f"- \"{c['text']}\"\n  → \"{c['rewrite']}\"" for c in d["claims"])
        propose("doc_fix", f"Update “{doc['name']}”", who, why + f" {len(d['claims'])} statement(s) now contradict {did.split(':')[1]}.",
                [doc["id"]], draft=fixes)

    for name, c in customers.items():
        if any(name in (x.get("decision") or "") or name in (x.get("reason") or "") for x in conflict_items
               if x["relation"] == "conflicts"):
            continue  # handled by the conflict task
        mail = emails.get(name, {})
        if mail.get("hold"):
            continue
        am = tools.resolve(c["account_manager"], prefer=("Person",)) if c.get("account_manager") else None
        draft = f"Subject: {mail.get('subject', '')}\n\n{mail.get('body', '')}" if mail else None
        propose("customer_notice", f"Tell {name} about the change", am,
                f"{name} integrates with {c['via_api']} (${c['arr']:,} ARR); {c['account_manager']} is their account manager.",
                [tools.resolve(name, prefer=("Customer",))["id"]], draft=draft)

    seen = set()
    for s in impact["services"]:
        if s["hops"] != 1 or s["service"] in seen:
            continue
        seen.add(s["service"])
        svc = resolve(s["service"], prefer=("Service",))
        if s.get("owner") and not s.get("owner_has_left"):
            who, why = resolve(s["owner"], prefer=("Person",)), f"{s['owner']} owns {s['service']} ({s['how'].lower()} the affected API)."
        else:
            who, sig = _successor(ctx, svc["id"])
            why = (f"{s['service']} {s['how'].lower()} the affected API and its owner {s.get('owner')} has left; "
                   f"{who['name'] if who else 'nobody'} knows it best ({sig}).")
        propose("service_change", f"Plan the change in {s['service']}", who, why, [svc["id"]],
                priority="high" if s.get("owner_has_left") else "normal")

    order = {"resolve_conflict": 0, "service_change": 1, "doc_fix": 2, "customer_notice": 3}
    proposals.sort(key=lambda p: (p["priority"] != "high", order.get(p["kind"], 9)))
    for i, prop in enumerate(proposals, start=1):
        prop["pid"] = f"p{i}"
    yield _ev("proposals", decision_id=did, items=proposals)
    yield _ev("done", decision_id=did, seconds=round(time.time() - t0, 1))


def approve(decision_id: str, items: list[dict]) -> dict:
    """Write approved proposals as Task nodes: (Task)-[:FOR]->(Decision), -[:ASSIGNED_TO]->(Person), -[:TARGETS]->(...)."""
    nodes, links = [], []
    for it in items:
        tid = f"task:{uuid.uuid4().hex[:8]}"
        db.run("CREATE (t:Task:Entity {id: $id, name: $title, title: $title, kind: $kind, status: 'open', "
               "priority: $prio, because: $because, draft: $draft, created: $at, at: $at})",
               {"id": tid, "title": it["title"], "kind": it.get("kind"), "prio": it.get("priority", "normal"),
                "because": it.get("because", ""), "draft": it.get("draft") or "", "at": config.TODAY})
        db.run("MATCH (t:Entity {id: $t}), (d:Entity {id: $d}) CREATE (t)-[:FOR]->(d)", {"t": tid, "d": decision_id})
        links.append({"source": tid, "type": "FOR", "target": decision_id})
        if it.get("assignee"):
            db.run("MATCH (t:Entity {id: $t}), (p:Entity {id: $p}) CREATE (t)-[:ASSIGNED_TO]->(p)",
                   {"t": tid, "p": it["assignee"]["id"]})
            links.append({"source": tid, "type": "ASSIGNED_TO", "target": it["assignee"]["id"]})
        for target in it.get("targets", []):
            db.run("MATCH (t:Entity {id: $t}), (x:Entity {id: $x}) CREATE (t)-[:TARGETS]->(x)", {"t": tid, "x": target})
            links.append({"source": tid, "type": "TARGETS", "target": target})
        nodes.append(slim(tools.by_id(tid)))
    return {"nodes": nodes, "links": links, "created": len(nodes)}


def presets() -> list[dict]:
    from . import dataset
    out = []
    for e in dataset.load().events:
        author = tools.by_id(e["author"])
        out.append({**e, "author_name": author["name"] if author else e["author"]})
    return out
