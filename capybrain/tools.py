"""Agent tools. Each tool is a handful of Cypher queries from queries.py over the company graph.

Every tool returns a ToolResult with:
  data     compact JSON for the model, where citable items carry a cite key (S1, S2, ...)
  nodes    the nodes it touched (the UI adds missing ones and highlights them)
  links    the relationships it walked (the UI animates them)
  cypher   the queries that ran (shown in the trace)
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

from . import dataset, db, embeddings
from . import queries as Q
from .seed import build_linker

TYPE_PREFIX = {"Service": "svc:", "Api": "api:", "Customer": "cust:", "Person": "person:", "Team": "team:",
               "Doc": "doc:", "Decision": "dec:", "Incident": "inc:", "Ticket": "ticket:", "Meeting": "mtg:"}
SLIM_KEYS = ("id", "type", "name", "title", "status", "at", "ts", "left", "key", "kind", "channel", "severity", "arr",
             "tier", "team", "number", "state", "priority", "doc", "summary", "assignee")


@lru_cache(maxsize=1)
def linker():
    return build_linker(dataset.load())


def slim(n: dict) -> dict:
    out = {k: n[k] for k in SLIM_KEYS if k in n and n[k] is not None}
    if "summary" in out:
        out["summary"] = out["summary"][:240]
    return out


def snippet(n: dict, size: int = 260) -> str:
    text = n.get("text") or n.get("summary") or n.get("description") or n.get("reason") or ""
    text = " ".join(str(text).split())
    return text if len(text) <= size else text[: size - 1] + "…"


def when(n: dict) -> str:
    return str(n.get("at") or n.get("ts") or n.get("updated") or "")[:10]


class Citations:
    """Hands out stable cite keys (S1, S2, ...) for the sources a conversation turn used."""

    def __init__(self) -> None:
        self.by_id: dict[str, str] = {}
        self.items: list[dict] = []

    def add(self, n: dict | None) -> str | None:
        if not n or not n.get("id"):
            return None
        if n["id"] not in self.by_id:
            key = f"S{len(self.items) + 1}"
            self.by_id[n["id"]] = key
            self.items.append({"key": key, "id": n["id"], "type": n.get("type"), "title": n.get("name") or n["id"],
                               "at": when(n), "snippet": snippet(n, 400)})
        return self.by_id[n["id"]]


@dataclass
class ToolResult:
    data: dict
    nodes: dict = field(default_factory=dict)
    links: list = field(default_factory=list)
    cypher: list = field(default_factory=list)
    summary: str = ""

    def node(self, n: dict | None) -> dict | None:
        if n and n.get("id"):
            self.nodes[n["id"]] = slim(n)
        return n

    def link(self, src: dict | str | None, rel: str, dst: dict | str | None) -> None:
        s = src.get("id") if isinstance(src, dict) else src
        d = dst.get("id") if isinstance(dst, dict) else dst
        if s and d:
            self.links.append({"source": s, "type": rel, "target": d})


class Ctx:
    """Per-turn context shared by the tools: citations plus the result being built."""

    def __init__(self, cites: Citations | None = None) -> None:
        self.cites = cites or Citations()

    def run(self, res: ToolResult, name: str, **params) -> list[dict]:
        res.cypher.append({"name": name, "cypher": Q.Q[name]["cypher"], "params": _show_params(params)})
        return db.to_json(db.run(Q.Q[name]["cypher"], params, ro=True))


def _show_params(params: dict) -> dict:
    return {k: ("<embedding>" if k == "vec" else v) for k, v in params.items()}


# --------------------------------------------------------------------------- resolution
def by_id(node_id: str) -> dict | None:
    rows = db.to_json(db.run(Q.NODE_BY_ID, {"id": node_id}, ro=True))
    return rows[0]["n"] if rows else None


def resolve(subject: str, prefer: tuple[str, ...] = ()) -> dict | None:
    """Turn a name the model or user wrote into a graph node: id → alias gazetteer → full-text."""
    subject = (subject or "").strip()
    if not subject:
        return None
    if re.match(r"^[a-z]+:[\w.\-]+$", subject):
        n = by_id(subject)
        if n:
            return n
    m = re.search(r"\b(?:D|ADR)-0*(\d+)\b", subject, re.I)
    if m and (not prefer or "Decision" in prefer):
        n = by_id(f"dec:D-{int(m.group(1)):03d}")
        if n:
            return n
    ids = linker().link(subject)
    if prefer:
        ids = sorted(ids, key=lambda i: 0 if any(i.startswith(TYPE_PREFIX.get(p, "?")) for p in prefer) else 1)
    for i in ids:
        n = by_id(i)
        if n:
            return n
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", subject) if len(t) > 2]
    for qstr in (" ".join(tokens), "|".join(tokens), "|".join(f"%{t}%" for t in tokens if len(t) > 4)):
        if not qstr:
            continue
        try:
            rows = db.to_json(db.run(Q.FULLTEXT_SEARCH, {"q": qstr, "k": 15}, ro=True))
        except Exception:
            continue
        nodes = [r["node"] for r in rows if r["node"]["type"] not in ("Message", "Claim")]
        if prefer:
            nodes = sorted(nodes, key=lambda n: 0 if n["type"] in prefer else 1)
        if nodes:
            return nodes[0]
    return None


def find_decision(ctx: Ctx, res: ToolResult, topic: str) -> dict | None:
    n = resolve(topic, prefer=("Decision",)) if re.search(r"\b(?:D|ADR)-\d+", topic, re.I) else None
    if n and n["type"] == "Decision":
        return n
    rows = ctx.run(res, "decision_search", k=3, vec=embeddings.embed(topic))
    return rows[0]["node"] if rows else None


# --------------------------------------------------------------------------- tools
def search(ctx: Ctx, query: str) -> ToolResult:
    res = ToolResult(data={})
    rows = ctx.run(res, "vector_search", k=10, vec=embeddings.embed(query))
    items = []
    for r in rows:
        n = r["node"]
        item = {"cite": ctx.cites.add(n), "type": n["type"], "title": n.get("name"), "date": when(n),
                "text": snippet(n)}
        if n["type"] == "Claim":
            item["in_doc"] = n.get("doc")
        items.append(item)
        res.node(n)
    res.data = {"query": query, "results": items}
    res.summary = f"{len(items)} matches"
    return res


def trace_decision(ctx: Ctx, topic: str) -> ToolResult:
    res = ToolResult(data={})
    d = find_decision(ctx, res, topic)
    if not d:
        res.data = {"error": f"no decision found for {topic!r}"}
        res.summary = "no decision found"
        return res
    row = ctx.run(res, "decision_trace", id=d["id"])[0]
    authors = {r["message"]: r["p"] for r in ctx.run(res, "evidence_authors", id=d["id"])}
    res.node(d)
    out = {"decision": {"cite": ctx.cites.add(d), "id": d["id"], "title": d["title"], "date": d.get("at"),
                        "status": d.get("status"), "summary": d.get("summary")}}
    out["decided_by"] = []
    for p in row["deciders"]:
        res.node(p), res.link(p, "DECIDED", d)
        out["decided_by"].append(p["name"] + (" (has left)" if p.get("status") == "departed" else ""))
    out["decided_in"] = []
    for m in row["meetings"]:
        res.node(m), res.link(d, "DECIDED_IN", m)
        out["decided_in"].append({"cite": ctx.cites.add(m), "meeting": m["name"], "notes": snippet(m, 500)})
    out["triggered_by"] = []
    for i in row["triggers"]:
        res.node(i), res.link(d, "TRIGGERED_BY", i)
        out["triggered_by"].append({"cite": ctx.cites.add(i), "incident": i["name"], "date": when(i), "what": snippet(i)})
        for t in ctx.run(res, "incident_thread", id=i["id"])[:3]:
            m = t["m"]
            res.node(m), res.link(m, "MENTIONS", i)
    out["documented_in"] = []
    for doc in row["docs"]:
        res.node(doc), res.link(d, "DOCUMENTED_IN", doc)
        out["documented_in"].append({"cite": ctx.cites.add(doc), "doc": doc["name"]})
    out["rejected_alternatives"] = []
    for a in row["rejected"]:
        res.node(a), res.link(d, "REJECTED", a)
        out["rejected_alternatives"].append({"option": a["option"], "why_rejected": a["reason"]})
    out["evidence"] = []
    for m in sorted(row["evidence"], key=lambda x: x.get("ts", "")):
        res.node(m), res.link(d, "EVIDENCED_BY", m)
        who = authors.get(m["id"])
        if who:
            res.node(who), res.link(who, "POSTED", m)
        out["evidence"].append({"cite": ctx.cites.add(m), "who": who["name"] if who else None,
                                "when": when(m), "channel": m.get("channel"), "said": m.get("text")})
    out["implemented_by"] = []
    for pr in row["prs"]:
        res.node(pr), res.link(d, "IMPLEMENTED_BY", pr)
        out["implemented_by"].append({"cite": ctx.cites.add(pr), "pr": pr["name"]})
    for x in row["affects"]:
        res.node(x), res.link(d, "AFFECTS", x)
    out["affects"] = [x["name"] for x in row["affects"]]
    for key, rel, rows in (("superseded_by", "SUPERSEDES", row["superseded_by"]),
                           ("supersedes", "SUPERSEDES", row["supersedes"]),
                           ("conflicts_with", "CONFLICTS_WITH", row["conflicts"])):
        out[key] = []
        for o in rows:
            res.node(o)
            if key == "superseded_by":
                res.link(o, rel, d)
            else:
                res.link(d, rel, o)
            out[key].append({"cite": ctx.cites.add(o), "decision": o["name"], "date": when(o), "status": o.get("status")})
    res.data = out
    res.summary = f"{d['name']} · {len(out['evidence'])} messages · {len(out['rejected_alternatives'])} rejected options"
    return res


def who_knows(ctx: Ctx, subject: str) -> ToolResult:
    res = ToolResult(data={})
    x = resolve(subject, prefer=("Service", "Api", "Customer", "Doc", "Team"))
    if not x:
        res.data = {"error": f"could not find {subject!r} in the graph"}
        res.summary = "not found"
        return res
    res.node(x)
    rows = ctx.run(res, "expertise", id=x["id"], limit=12)
    owners = ctx.run(res, "owners", id=x["id"])
    out = {"subject": {"name": x["name"], "type": x["type"]}, "owners": [], "left_the_company": [], "people_to_ask": []}
    for o in owners:
        if o.get("team"):
            res.node(o["team"]), res.link(o["team"], "OWNS", x)
            out["owning_team"] = o["team"]["name"]
        if o.get("p"):
            p = o["p"]
            res.node(p), res.link(p, "OWNS", x)
            out["owners"].append({"name": p["name"], "status": p.get("status"),
                                  "owner_until": o.get("until"), "left_company": p.get("left")})
    if out["owners"] and all(o["status"] == "departed" for o in out["owners"]):
        out["warning"] = f"{x['name']} has no active owner: its owner has left the company."
    for r in rows:
        p = r["p"]
        signals = {k: r[k] for k in ("authored", "reviewed", "discussed", "docs", "meetings", "decisions", "tickets") if r[k]}
        entry = {"name": p["name"], "title": p.get("title"), "team": r["team"], "score": round(r["score"], 1),
                 "evidence_counts": signals}
        if p.get("status") == "departed":
            entry["left"] = p.get("left")
            out["left_the_company"].append(entry)
            res.node(p)
            continue
        if len(out["people_to_ask"]) < 4:
            examples = []
            for e in ctx.run(res, "expertise_evidence", person=p["id"], id=x["id"], limit=3):
                n = e["e"]
                res.node(n), res.link(p, e["how"], n), res.link(n, "ABOUT", x)
                examples.append({"cite": ctx.cites.add(n), "what": n["name"], "date": when(n)})
            entry["examples"] = examples
            res.node(p)
            out["people_to_ask"].append(entry)
    res.data = out
    top = ", ".join(e["name"] for e in out["people_to_ask"][:3])
    res.summary = f"{x['name']}: ask {top}" if top else f"{x['name']}: nobody found"
    return res


def impact_of(ctx: Ctx, subject: str) -> ToolResult:
    res = ToolResult(data={})
    x = resolve(subject, prefer=("Api", "Service", "Customer"))
    if not x:
        res.data = {"error": f"could not find {subject!r} in the graph"}
        res.summary = "not found"
        return res
    res.node(x)
    out = {"subject": {"name": x["name"], "type": x["type"]}}
    out["services"] = []
    for r in ctx.run(res, "impact_services", id=x["id"]):
        s = r["s"]
        res.node(s)
        for a, rel, b in zip(r["path_ids"], r["path_rels"], r["path_ids"][1:]):
            res.link(a, rel, b)
        owner = r.get("owner")
        if owner:
            res.node(owner), res.link(owner, "OWNS", s)
        out["services"].append({"service": s["name"], "hops": r["hops"], "how": r["via"],
                                "owner": owner["name"] if owner else None,
                                "owner_has_left": bool(owner and owner.get("status") == "departed"),
                                "team": r["team"]["name"] if r.get("team") else None})
    out["customers"] = []
    for r in ctx.run(res, "impact_customers", id=x["id"]):
        c, am = r["c"], r.get("am")
        res.node(c), res.node(r["api"]), res.link(c, "INTEGRATES_WITH", r["api"])
        if am:
            res.node(am), res.link(am, "ACCOUNT_MANAGER_OF", c)
        out["customers"].append({"cite": ctx.cites.add(c), "customer": c["name"], "arr": c.get("arr"),
                                 "via_api": r["api"]["name"], "account_manager": am["name"] if am else None})
    out["decisions_and_promises"] = []
    for r in ctx.run(res, "impact_decisions", id=x["id"]):
        dec = r["dec"]
        res.node(dec), res.link(dec, "AFFECTS", x)
        out["decisions_and_promises"].append({"cite": ctx.cites.add(dec), "decision": dec["name"], "date": when(dec),
                                              "summary": dec.get("summary"),
                                              "decided_by": [p["name"] for p in r["deciders"]]})
    docs: dict[str, dict] = {}
    for r in ctx.run(res, "impact_claims", id=x["id"]):
        d, cl = r["d"], r["cl"]
        res.node(d), res.link(d, "ABOUT", x)
        entry = docs.setdefault(d["id"], {"cite": ctx.cites.add(d), "doc": d["name"], "updated": d.get("updated"),
                                          "status": d.get("status"), "authors": [a["name"] for a in r["authors"]],
                                          "statements": []})
        if len(entry["statements"]) < 3:
            entry["statements"].append(cl["text"])
    out["docs"] = list(docs.values())
    out["open_tickets"] = []
    for r in ctx.run(res, "impact_tickets", id=x["id"]):
        t, p = r["t"], r.get("p")
        res.node(t), res.link(t, "ABOUT", x)
        out["open_tickets"].append({"cite": ctx.cites.add(t), "ticket": t["name"], "status": t.get("status"),
                                    "assignee": p["name"] if p else "unassigned"})
    res.data = out
    res.summary = (f"{len(out['services'])} services · {len(out['customers'])} customers · "
                   f"{len(out['decisions_and_promises'])} decisions · {len(out['docs'])} docs · {len(out['open_tickets'])} tickets")
    return res


def open_work(ctx: Ctx, subject: str) -> ToolResult:
    res = ToolResult(data={})
    entity = resolve(subject, prefer=("Decision", "Api", "Service", "Customer"))
    decisions: dict[str, dict] = {}
    if entity and entity["type"] == "Decision":
        decisions[entity["id"]] = entity
    elif entity:
        for r in ctx.run(res, "decisions_with_tasks", id=entity["id"]):
            decisions[r["d"]["id"]] = r["d"]
    if not decisions:
        rows = ctx.run(res, "decision_search", k=1, vec=embeddings.embed(subject))
        if rows and rows[0]["score"] < 0.3:
            decisions[rows[0]["node"]["id"]] = rows[0]["node"]
    if not entity and not decisions:
        res.data = {"error": f"could not find {subject!r}"}
        res.summary = "not found"
        return res
    tasks, seen_tasks = [], set()
    for target in list(decisions.values()) + ([entity] if entity else []):
        res.node(target)
        for r in ctx.run(res, "open_tasks", id=target["id"]):
            t, p = r["t"], r.get("p")
            if t["id"] in seen_tasks:
                continue
            seen_tasks.add(t["id"])
            res.node(t), res.link(t, "FOR", target)
            if p:
                res.node(p), res.link(t, "ASSIGNED_TO", p)
            tasks.append({"cite": ctx.cites.add(t), "task": t.get("title"), "kind": t.get("kind"),
                          "status": t.get("status"), "priority": t.get("priority"),
                          "assignee": p["name"] if p else None, "because": t.get("because")})
    tickets, ticket_targets = [], [entity] if entity else []
    for d in decisions.values():
        ticket_targets += [r["x"] for r in db.to_json(db.run(
            "MATCH (:Decision {id: $id})-[:AFFECTS]->(x) RETURN x", {"id": d["id"]}, ro=True))]
    seen_t = set()
    for target in ticket_targets:
        for r in ctx.run(res, "impact_tickets", id=target["id"]):
            t, p = r["t"], r.get("p")
            if t["id"] in seen_t:
                continue
            seen_t.add(t["id"])
            res.node(t), res.link(t, "ABOUT", target)
            tickets.append({"cite": ctx.cites.add(t), "ticket": t["name"], "status": t.get("status"),
                            "assignee": p["name"] if p else "unassigned"})
    res.data = {"subject": {"name": (entity or next(iter(decisions.values())))["name"]},
                "decisions": [{"cite": ctx.cites.add(d), "decision": d["name"], "date": d.get("at"),
                               "status": d.get("status")} for d in decisions.values()],
                "tasks": tasks, "open_tickets": tickets}
    done = sum(1 for t in tasks if t["status"] == "done")
    res.summary = f"{len(tasks)} tasks ({done} done) · {len(tickets)} open tickets"
    return res


def get_details(ctx: Ctx, id: str) -> ToolResult:
    res = ToolResult(data={})
    n = by_id(id) or resolve(id)
    if not n:
        res.data = {"error": f"no node {id!r}"}
        return res
    res.node(n)
    neigh = ctx.run(res, "neighbours", id=n["id"], limit=40)
    links = []
    for r in neigh:
        m = r["m"]
        res.node(m)
        if r["outgoing"]:
            res.link(n, r["rel"], m)
        else:
            res.link(m, r["rel"], n)
        links.append(f"{'->' if r['outgoing'] else '<-'}{r['rel']} {m['type']}: {m.get('name')}"
                     + (" (has left)" if m.get("status") == "departed" else ""))
    data = {"cite": ctx.cites.add(n), **slim(n), "text": (n.get("text") or n.get("summary") or "")[:3000], "connections": links}
    if n["type"] == "Message" and n.get("id"):
        root = n["id"]
        parent = [r for r in neigh if r["rel"] == "REPLY_TO" and r["outgoing"]]
        if parent:
            root = parent[0]["m"]["id"]
        data["thread"] = [{"cite": ctx.cites.add(r["m"]), "who": r["author"]["name"], "said": r["m"]["text"]}
                          for r in ctx.run(res, "thread", root=root)]
    res.data = data
    res.summary = f"{n['type']}: {n.get('name')}"
    return res


FORBIDDEN = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|LOAD\s+CSV)\b", re.I)


def graph_query(ctx: Ctx, cypher: str) -> ToolResult:
    res = ToolResult(data={})
    res.cypher.append({"name": "graph_query (model-written, read-only)", "cypher": cypher, "params": {}})
    if FORBIDDEN.search(cypher):
        res.data = {"error": "only read queries are allowed"}
        res.summary = "rejected: not read-only"
        return res
    try:
        rows = db.to_json(db.run(cypher, ro=True))  # GRAPH.RO_QUERY: the database itself refuses writes
    except Exception as e:  # noqa: BLE001 - surface the database error to the model
        res.data = {"error": str(e)[:300]}
        res.summary = "query error"
        return res

    def compact(v):
        if isinstance(v, dict) and v.get("id") and v.get("type"):
            res.node(v)
            return {"cite": ctx.cites.add(v), **{k: (str(val)[:200] if isinstance(val, str) else val)
                                               for k, val in slim(v).items()}}
        if isinstance(v, dict):
            return {k: compact(val) for k, val in v.items()}
        if isinstance(v, list):
            return [compact(i) for i in v[:30]]
        if isinstance(v, str):
            return v[:300]
        return v

    res.data = {"rows": [compact(r) for r in rows[:30]], "row_count": len(rows)}
    res.summary = f"{len(rows)} rows"
    return res


GRAPH_SCHEMA = (
    "Nodes (all have id, name): Person{title,status:'active'|'departed',left}, Team, Service{tier,description}, "
    "Api{status}, Customer{arr,tier}, Decision{title,summary,at,status:'active'|'superseded'}, Doc{title,kind,updated,status}, "
    "Claim{text,status:'current'|'stale'}, Message{text,ts,channel}, Ticket{key,title,status,priority}, PR{number,title,state}, "
    "Meeting{title,at}, Incident{key,title,severity,at}, Task{title,status,kind}. "
    "Relationships: (Person)-[:MEMBER_OF]->(Team); (Person)-[:REPORTS_TO]->(Person); (Team|Person)-[:OWNS {until}]->(Service); "
    "(Service)-[:DEPENDS_ON]->(Service); (Service)-[:EXPOSES|CALLS|AUTHENTICATES]->(Api); (Customer)-[:INTEGRATES_WITH]->(Api); "
    "(Person)-[:ACCOUNT_MANAGER_OF]->(Customer); (Person)-[:AUTHORED]->(Doc|PR); (Person)-[:REVIEWED]->(PR); (PR)-[:TOUCHES]->(Service); "
    "(PR)-[:FIXES]->(Ticket); (Person)-[:POSTED]->(Message); (Message)-[:REPLY_TO]->(Message); (Message|Doc|Ticket|PR|Meeting)-[:MENTIONS]->(any); "
    "(Ticket)-[:ABOUT]->(Service); (Ticket)-[:ASSIGNED_TO]->(Person); (Ticket)-[:FOR_CUSTOMER]->(Customer); (Person)-[:ATTENDED]->(Meeting); "
    "(Person)-[:DECIDED]->(Decision); (Decision)-[:DECIDED_IN]->(Meeting); (Decision)-[:AFFECTS]->(any); "
    "(Decision)-[:SUPERSEDES|CONFLICTS_WITH]->(Decision); (Decision)-[:TRIGGERED_BY]->(Incident); (Doc)-[:STATES]->(Claim)-[:ABOUT]->(any); "
    "(Task)-[:FOR]->(Decision); (Task)-[:ASSIGNED_TO]->(Person); (Person)-[:COLLABORATES {weight}]->(Person). "
    "Match names case-insensitively with toLower(n.name) CONTAINS 'x'. Always add LIMIT."
)


def _fn(name: str, description: str, params: dict) -> dict:
    return {"type": "function", "function": {"name": name, "description": description,
                                             "parameters": {"type": "object", "properties": params,
                                                            "required": list(params)}}}


TOOL_SPECS = [
    _fn("trace_decision", "Explain WHY something was decided. Finds the decision and walks the graph to who decided it, "
        "the meeting, the incident that triggered it, rejected alternatives, the chat messages that are its evidence, and the PRs "
        "that implemented it. Use for 'why did we...' questions.",
        {"topic": {"type": "string", "description": "what the decision was about, e.g. 'webhooks queue'"}}),
    _fn("who_knows", "Find WHO owns or knows a service, API, customer or doc, ranked by evidence in the graph (PRs authored "
        "and reviewed, messages, docs, meetings, tickets). Flags owners who have left the company. Use for 'who can help', "
        "'who owns', 'who should I ask'.",
        {"subject": {"type": "string", "description": "a service, API, customer or doc name, e.g. 'ledger-service'"}}),
    _fn("impact_of", "Find WHAT IS AFFECTED if a service or API changes or goes away: services that depend on it and their "
        "owners, customers integrated with it and their account managers, active decisions and promises about it, docs that "
        "describe it, open tickets. Use for 'what breaks', 'who is affected', 'which customers'.",
        {"subject": {"type": "string", "description": "a service or API name, e.g. 'REST API v1'"}}),
    _fn("open_work", "List follow-up tasks and open tickets for a decision, service or API. Use for 'what's left', 'status', "
        "'who is doing what'.",
        {"subject": {"type": "string", "description": "a decision topic, service or API"}}),
    _fn("search", "Semantic search over everything the company wrote: Slack messages, docs, tickets, PRs, meeting notes, "
        "decisions. Use for open questions or to find starting points.",
        {"query": {"type": "string"}}),
    _fn("get_details", "Read one node in full (doc, message thread, ticket, PR, meeting, person...) with its direct "
        "connections. Pass an id from earlier results, or a name.",
        {"id": {"type": "string"}}),
    _fn("graph_query", "Run a READ-ONLY Cypher query on the company graph for structured questions the other tools cannot "
        "answer. Schema: " + GRAPH_SCHEMA,
        {"cypher": {"type": "string"}}),
]

TOOLS = {"search": search, "trace_decision": trace_decision, "who_knows": who_knows, "impact_of": impact_of,
         "open_work": open_work, "get_details": get_details, "graph_query": graph_query}


def call(ctx: Ctx, name: str, args: dict) -> ToolResult:
    fn = TOOLS.get(name)
    if not fn:
        return ToolResult(data={"error": f"unknown tool {name}"}, summary="unknown tool")
    try:
        return fn(ctx, **args)
    except TypeError as e:
        return ToolResult(data={"error": f"bad arguments for {name}: {e}"}, summary="bad arguments")
