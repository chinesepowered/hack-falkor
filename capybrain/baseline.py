"""Baseline for comparison: plain vector RAG over the same text, no graph.

Same LLM, same embeddings, same FalkorDB vector index, top-k chunks from messages, docs, doc
statements, tickets, PRs and meeting notes. What it does NOT get is the graph: no ownership, no
CRM integrations, no who-has-left, no decision links. That is exactly the difference we show.
"""
from __future__ import annotations

import time

from . import config, db, embeddings, llm
from . import queries as Q

TEXT_TYPES = {"Message", "Doc", "Claim", "Ticket", "PR", "Meeting", "Incident"}

SYSTEM = """You answer questions about the company Tallybird using ONLY the numbered context snippets.
Cite snippets like [3]. If the snippets don't contain the answer, say what is missing. Be brief: one sentence, then short bullets.
Today is {today}."""


def answer(question: str, k: int = 8) -> dict:
    t0 = time.time()
    rows = db.to_json(db.run(Q.VECTOR_SEARCH, {"k": k * 3, "vec": embeddings.embed(question)}, ro=True))
    chunks = [r["node"] for r in rows if r["node"]["type"] in TEXT_TYPES][:k]
    context = "\n".join(f"[{i}] ({c['type']}, {str(c.get('at') or c.get('ts') or '')[:10]}) {c.get('name')}: "
                        f"{' '.join(str(c.get('text') or '').split())[:600]}" for i, c in enumerate(chunks, start=1))
    text = llm.complete([{"role": "system", "content": SYSTEM.format(today=config.TODAY)},
                         {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
                        max_tokens=2500, temperature=0.2)
    return {"answer": text, "seconds": round(time.time() - t0, 1),
            "snippets": [{"n": i, "id": c["id"], "type": c["type"], "title": c.get("name"),
                          "at": str(c.get("at") or c.get("ts") or "")[:10]} for i, c in enumerate(chunks, start=1)]}
