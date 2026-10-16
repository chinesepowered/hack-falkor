import os

# Tests run against their own graphs so they never touch the demo graph.
os.environ.setdefault("CAPYBRAIN_GRAPH", "tallybird_test")

import pytest  # noqa: E402

from capybrain import config, db, seed  # noqa: E402




@pytest.fixture(scope="session", autouse=True)
def seeded_graph():
    """Build the seed graph once per session and copy it to the live test graph."""
    seed.build(config.SEED_GRAPH)
    seed.reset()
    yield
    for name in (config.GRAPH, config.SEED_GRAPH, "tallybird_ablation"):
        try:
            db.graph(name).delete()
        except Exception:
            pass


@pytest.fixture()
def fresh_graph():
    """Restore the live test graph from the seed copy (GRAPH.COPY) before a test that writes."""
    seed.reset()
    yield
    seed.reset()


def has_llm() -> bool:
    return bool(config.LLM_API_KEY)
