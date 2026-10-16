"""Local text embeddings (BAAI/bge-small-en-v1.5 via fastembed), cached on disk."""
from __future__ import annotations

import hashlib
import pickle
from functools import lru_cache

from . import config

_CACHE_FILE = config.CACHE_DIR / "embeddings.pkl"
_cache: dict[str, list[float]] | None = None


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding(config.EMBED_MODEL, cache_dir=str(config.CACHE_DIR / "fastembed"))


def _load_cache() -> dict[str, list[float]]:
    global _cache
    if _cache is None:
        try:
            _cache = pickle.loads(_CACHE_FILE.read_bytes())
        except Exception:
            _cache = {}
    return _cache


def _key(text: str) -> str:
    return hashlib.sha1(f"{config.EMBED_MODEL}\n{text}".encode()).hexdigest()


def embed_many(texts: list[str]) -> list[list[float]]:
    cache = _load_cache()
    missing = [t for t in dict.fromkeys(texts) if _key(t) not in cache]
    if missing:
        for t, v in zip(missing, _model().embed(missing, batch_size=64)):
            cache[_key(t)] = [round(float(x), 6) for x in v]
        config.CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_bytes(pickle.dumps(cache))
    return [cache[_key(t)] for t in texts]


def embed(text: str) -> list[float]:
    return embed_many([text])[0]
