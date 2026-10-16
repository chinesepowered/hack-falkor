"""Thin helpers around the FalkorDB client: run Cypher, convert results to JSON."""
from __future__ import annotations

from typing import Any

from falkordb import FalkorDB
from falkordb.edge import Edge
from falkordb.node import Node
from falkordb.path import Path

from . import config

_client: FalkorDB | None = None

# Labels every node carries for indexing; hidden from the UI.
INTERNAL_LABELS = {"Entity", "Searchable", "Active"}


def client() -> FalkorDB:
    global _client
    if _client is None:
        _client = FalkorDB(host=config.FALKORDB_HOST, port=config.FALKORDB_PORT,
                           password=config.FALKORDB_PASSWORD)
    return _client


def graph(name: str | None = None):
    return client().select_graph(name or config.GRAPH)


def run(cypher: str, params: dict | None = None, *, ro: bool = False, graph_name: str | None = None) -> list[dict]:
    """Run a query and return rows as dicts. ro=True uses GRAPH.RO_QUERY (writes are rejected)."""
    g = graph(graph_name)
    res = g.ro_query(cypher, params) if ro else g.query(cypher, params)
    header = [h[1] for h in res.header]
    return [dict(zip(header, row)) for row in res.result_set]


def label_of(n: Node) -> str:
    labels = [lbl for lbl in n.labels if lbl not in INTERNAL_LABELS]
    return labels[0] if labels else "Entity"


def node_json(n: Node) -> dict:
    props = {k: v for k, v in n.properties.items() if k != "embedding"}
    return {"id": props.get("id"), "type": label_of(n), **props}


def to_json(value: Any) -> Any:
    """Recursively convert FalkorDB result values into JSON-friendly data."""
    if isinstance(value, Node):
        return node_json(value)
    if isinstance(value, Edge):
        return {"type": value.relation, **{k: v for k, v in value.properties.items()}}
    if isinstance(value, Path):
        return {"nodes": [node_json(n) for n in value.nodes()], "edges": [e.relation for e in value.edges()]}
    if isinstance(value, list):
        return [to_json(v) for v in value]
    if isinstance(value, dict):
        return {k: to_json(v) for k, v in value.items()}
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
