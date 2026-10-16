"""Capy, the agent: an LLM tool loop over the company graph, streamed as events for the UI."""
from __future__ import annotations

import json
import re
import time
import uuid
from typing import Iterator

from . import config, db, embeddings, llm, tools
from . import queries as Q

MAX_STEPS = 6

SYSTEM = """You are Capy, the company brain of Tallybird, a fictional B2B invoicing and payments company. \
You answer questions about how the company works using ONLY the company knowledge graph, which you reach through tools.

How to work:
- Pick the most specific tool: trace_decision for "why did we...", who_knows for "who owns / who can help", \
impact_of for "what breaks / who is affected / which customers", open_work for "what's left / status". \
Use search or get_details to read raw messages and docs, and graph_query only when nothing else fits.
- Usually one or two tool calls are enough. Do not call the same tool twice with the same arguments.
- Never invent people, dates or facts. If the graph does not contain the answer, say so.
- People can have left the company (status "departed"). Never recommend someone who has left as the person to ask; \
say they left and point to who knows the area now.
- Cite sources inline with the cite keys from tool results in square brackets, like [S3] or [S2][S5]. \
Only use keys that appeared in tool results. Cite the most direct evidence (messages, docs, meetings, tickets).

Answer style: friendly and calm, but brief and concrete. Lead with the answer in one sentence, then a few short \
bullets with names, dates and citations. Use **bold** for names of people, customers and services. No headings. \
Today is {today}."""


def _sse_nodes(res: tools.ToolResult) -> dict:
    return {"nodes": list(res.nodes.values()), "links": res.links}


# --------------------------------------------------------------------------- memory
def recall(question: str) -> dict | None:
    """Agent memory: the closest earlier answer, and whether its sources have gone stale since."""
    try:
        rows = db.to_json(db.run(Q.ANSWER_SEARCH, {"k": 1, "vec": embeddings.embed(question)}, ro=True))
    except Exception:
        return None
    if not rows or rows[0]["score"] > 0.08:
        return None
    r = rows[0]
    stale = [s for s in r["sources"] if s.get("status") in ("stale", "superseded", "departed")]
    return {"id": r["node"]["id"], "question": r["node"]["question"], "answer": r["node"]["text"],
            "at": r["node"].get("at"), "sources": len(r["sources"]),
            "stale_sources": [{"id": s["id"], "name": s.get("name"), "status": s.get("status")} for s in stale]}


def remember(question: str, answer: str, cited_ids: list[str]) -> str:
    aid = f"answer:{uuid.uuid4().hex[:10]}"
    db.run("CREATE (a:Answer:Entity {id: $id, name: $name, question: $q, text: $t, at: $at}) "
           "SET a.embedding = vecf32($vec)",
           {"id": aid, "name": "Q: " + question[:60], "q": question, "t": answer, "at": config.TODAY,
            "vec": embeddings.embed(question)})
    if cited_ids:
        db.run("MATCH (a:Answer {id: $id}) UNWIND $cited AS cid MATCH (s:Entity {id: cid}) CREATE (a)-[:CITES]->(s)",
               {"id": aid, "cited": cited_ids})
    return aid


# --------------------------------------------------------------------------- loop
def ask(question: str, history: list[dict] | None = None, use_memory: bool = True) -> Iterator[dict]:
    t0 = time.time()
    ctx = tools.Ctx()
    messages: list[dict] = [{"role": "system", "content": SYSTEM.format(today=config.TODAY)}]
    for h in (history or [])[-6:]:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            messages.append({"role": h["role"], "content": str(h["content"])[:2000]})

    memory = recall(question) if use_memory else None
    if memory:
        yield {"type": "memory", **memory}
        note = (f"Memory: on {memory['at']} you answered a very similar question (\"{memory['question']}\"). "
                f"Your earlier answer was: {memory['answer'][:600]}")
        if memory["stale_sources"]:
            note += (" WARNING: some sources of that answer have changed since (" +
                     ", ".join(f"{s['name']} is now {s['status']}" for s in memory["stale_sources"]) +
                     "). Do not reuse it; check the graph again and mention what changed.")
        messages.append({"role": "system", "content": note})
    messages.append({"role": "user", "content": question})

    seen_calls: set[str] = set()
    for step in range(MAX_STEPS):
        yield {"type": "status", "text": "Capy is thinking…" if step == 0 else "Capy is reading the results…"}
        turn = None
        streamed = False
        try:
            for kind, val in llm.stream_turn(messages, tools.TOOL_SPECS if step < MAX_STEPS - 1 else None):
                if kind == "reasoning":
                    yield {"type": "reasoning", "text": val}
                elif kind == "content":
                    streamed = True
                    yield {"type": "answer_delta", "text": val}
                else:
                    turn = val
        except Exception as e:  # noqa: BLE001
            yield {"type": "error", "message": f"LLM error: {e}"}
            return
        if turn.tool_calls:
            if streamed:
                yield {"type": "answer_reset"}
            messages.append({"role": "assistant", "content": turn.content or "",
                             "tool_calls": [{"id": tc.id, "type": "function",
                                             "function": {"name": tc.name, "arguments": tc.arguments or "{}"}}
                                            for tc in turn.tool_calls]})
            for tc in turn.tool_calls:
                args = tc.args()
                key = f"{tc.name}:{json.dumps(args, sort_keys=True)}"
                yield {"type": "tool_call", "id": tc.id, "name": tc.name, "args": args}
                if key in seen_calls:
                    res = tools.ToolResult(data={"note": "You already ran this exact call; use the earlier result."},
                                           summary="repeat call skipped")
                else:
                    seen_calls.add(key)
                    res = tools.call(ctx, tc.name, args)
                yield {"type": "tool_result", "id": tc.id, "name": tc.name, "summary": res.summary,
                       "cypher": res.cypher, **_sse_nodes(res)}
                messages.append({"role": "tool", "tool_call_id": tc.id,
                                 "content": json.dumps(res.data, default=str, ensure_ascii=False)[:14000]})
            continue

        answer = turn.content or "I couldn't find that in the company graph."
        keys = set(re.findall(r"S\d+", " ".join(re.findall(r"\[(S\d+(?:\s*[,;]\s*S\d+)*)\]", answer))))
        cited = [c for c in ctx.cites.items if c["key"] in keys]
        answer_id = None
        if use_memory:
            try:
                answer_id = remember(question, answer, [c["id"] for c in cited])
            except Exception:  # noqa: BLE001 - memory is best effort
                answer_id = None
        yield {"type": "answer", "text": answer, "sources": ctx.cites.items, "cited": [c["key"] for c in cited],
               "answer_id": answer_id, "seconds": round(time.time() - t0, 1)}
        return
    yield {"type": "error", "message": "Capy ran out of steps."}
