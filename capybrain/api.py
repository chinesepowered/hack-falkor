"""HTTP API (FastAPI). Streaming endpoints use server-sent events: one JSON object per `data:` line."""
from __future__ import annotations

import json
import threading
from typing import Iterator

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, baseline, config, db, ripple, seed, tools, xray
from . import queries as Q

app = FastAPI(title="CapyBrain", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
_write_lock = threading.Lock()


def sse(gen: Iterator[dict]) -> StreamingResponse:
    def stream():
        try:
            for ev in gen:
                yield f"data: {json.dumps(ev, default=str, ensure_ascii=False)}\n\n"
        except Exception as e:  # noqa: BLE001 - report errors to the UI instead of dropping the stream
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.on_event("startup")
def _startup() -> None:
    seed.ensure_seeded()


# --------------------------------------------------------------------------- read
@app.get("/api/health")
def health() -> dict:
    stats = db.run(Q.STATS, ro=True)
    return {"ok": True, "graph": config.GRAPH, "model": config.LLM_MODEL, "llm_configured": bool(config.LLM_API_KEY),
            "today": config.TODAY, "counts": {r["label"]: r["c"] for r in stats},
            "edges": db.run("MATCH ()-[r]->() RETURN count(r) AS c", ro=True)[0]["c"]}


@app.get("/api/graph")
def graph() -> dict:
    nodes = [tools.slim(r["n"]) for r in db.to_json(db.run(Q.OVERVIEW_NODES, ro=True))]
    links = db.run(Q.OVERVIEW_EDGES, ro=True)
    return {"nodes": nodes, "links": links}


@app.get("/api/node/{node_id:path}")
def node(node_id: str) -> dict:
    n = tools.by_id(node_id)
    if not n:
        raise HTTPException(404, f"no node {node_id}")
    neigh = db.to_json(db.run(Q.NEIGHBOURS, {"id": node_id, "limit": 60}, ro=True))
    out = {"node": n, "neighbours": [{"rel": r["rel"], "outgoing": r["outgoing"], "node": tools.slim(r["m"])} for r in neigh]}
    if n["type"] == "Message":
        parent = [r for r in neigh if r["rel"] == "REPLY_TO" and r["outgoing"]]
        root = parent[0]["m"]["id"] if parent else node_id
        out["thread"] = [{"node": tools.slim(r["m"]), "text": r["m"].get("text"), "author": r["author"]["name"]}
                         for r in db.to_json(db.run(Q.THREAD, {"root": root}, ro=True))]
    if n["type"] == "Doc":
        out["claims"] = db.to_json(db.run(
            "MATCH (:Doc {id: $id})-[:STATES]->(c:Claim) RETURN c.id AS id, c.text AS text, c.status AS status, "
            "c.stale_why AS why, c.rewrite AS rewrite ORDER BY c.ord", {"id": node_id}, ro=True))
    return out


@app.get("/api/xray")
def get_xray() -> dict:
    return xray.xray()


@app.get("/api/events")
def events() -> list[dict]:
    return ripple.presets()


@app.get("/api/queries")
def get_queries() -> dict:
    return Q.Q


# --------------------------------------------------------------------------- agent
class AskBody(BaseModel):
    question: str
    history: list[dict] = []
    memory: bool = True


@app.post("/api/ask")
def ask(body: AskBody) -> StreamingResponse:
    return sse(agent.ask(body.question, body.history, use_memory=body.memory))


class BaselineBody(BaseModel):
    question: str


@app.post("/api/baseline")
def run_baseline(body: BaselineBody) -> dict:
    return baseline.answer(body.question)


# --------------------------------------------------------------------------- ripple
class IngestBody(BaseModel):
    text: str
    author: str = "person:hannah"
    channel: str = "chan:announcements"
    ts: str | None = None


@app.post("/api/ingest")
def ingest(body: IngestBody) -> StreamingResponse:
    def locked():
        with _write_lock:
            yield from ripple.ingest(body.text, body.author, body.channel, body.ts)
    return sse(locked())


class ApproveBody(BaseModel):
    decision_id: str
    items: list[dict]


@app.post("/api/tasks/approve")
def approve(body: ApproveBody) -> dict:
    with _write_lock:
        return ripple.approve(body.decision_id, body.items)


@app.post("/api/reset")
def reset() -> dict:
    with _write_lock:
        seed.reset()
    return {"ok": True}


# --------------------------------------------------------------------------- frontend
if config.FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=config.FRONTEND_DIST / "assets"), name="assets")

    @app.get("/{path:path}")
    def spa(path: str):
        f = config.FRONTEND_DIST / path
        if path and f.is_file():
            return FileResponse(f)
        return FileResponse(config.FRONTEND_DIST / "index.html")
