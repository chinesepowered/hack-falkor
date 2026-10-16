"""Runtime configuration, read from environment variables (and a local .env file)."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

FALKORDB_HOST = os.getenv("FALKORDB_HOST", "localhost")
FALKORDB_PORT = int(os.getenv("FALKORDB_PORT", "6379"))
FALKORDB_PASSWORD = os.getenv("FALKORDB_PASSWORD") or None

# The live graph the app reads and writes, and the pristine copy used for resets.
GRAPH = os.getenv("CAPYBRAIN_GRAPH", "tallybird")
SEED_GRAPH = f"{GRAPH}_seed"

# Any OpenAI-compatible chat endpoint with tool calling (W&B Inference, vLLM, Ollama, ...).
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.inference.wandb.ai/v1")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "Qwen/Qwen3.8-27B")
# Extra request body that turns off the model's reasoning for fast structured calls (vLLM / Qwen style).
LLM_NO_THINK = json.loads(os.getenv("LLM_NO_THINK", '{"chat_template_kwargs": {"enable_thinking": false}}'))

EMBED_MODEL = os.getenv("EMBED_MODEL", "BAAI/bge-small-en-v1.5")
EMBED_DIM = 384

DATA_DIR = Path(os.getenv("CAPYBRAIN_DATA", ROOT / "data" / "tallybird"))
CACHE_DIR = Path(os.getenv("CAPYBRAIN_CACHE", ROOT / ".cache"))
FRONTEND_DIST = ROOT / "frontend" / "dist"

# "Today" in the fictional company, so relative dates in the demo stay stable.
TODAY = os.getenv("CAPYBRAIN_TODAY", "2026-10-16")
