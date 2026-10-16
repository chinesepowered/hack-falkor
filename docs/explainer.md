# How CapyBrain works (team explainer)

This is the cheat sheet for explaining CapyBrain to judges: what each part does, why it is built that way,
and the questions people usually ask. Everything here maps to a file you can open.

## The one-sentence version

CapyBrain puts a company's people, teams, services, APIs, customers, decisions, docs, chat, tickets and PRs
into one FalkorDB graph; an agent answers questions by walking that graph (so every answer is a path with
citations), and when a new message changes something, the brain updates itself, finds what went stale and
drafts the follow-up work, routed through the ownership graph.

## The three things it does

| Mode | What the user sees | What runs | Code |
|---|---|---|---|
| **Ask** | A cited answer, and the trail lighting up on the graph | LLM tool loop; every tool is a set of Cypher queries | `capybrain/agent.py`, `capybrain/tools.py` |
| **A change lands** | A ripple through the graph, stale docs turning red, follow-up tasks to approve | Extraction → Decision node → impact traversal → three LLM judges in parallel → task routing | `capybrain/ripple.py` |
| **Org X-ray** | Real working groups, hidden connectors, knowledge at risk | `algo.labelPropagation`, `algo.betweenness`, `algo.pageRank`, plus Cypher aggregations | `capybrain/xray.py` |

## Data model in one breath

Nodes: `Person, Team, Service, Api, Customer, Decision, Alternative, Doc, Claim, Message, Channel, Ticket, PR,
Meeting, Incident, Task, Answer`. Every node also has the `Entity` label (index on `id`, full-text on
`name`/`aka`); nodes with text also have `Searchable` (vector index on `embedding`).

Key relationships:
- org: `MEMBER_OF`, `REPORTS_TO`, `OWNS {until}` (person or team → service), `DEPENDS_ON`, `EXPOSES|CALLS|AUTHENTICATES` (service → API)
- customers: `INTEGRATES_WITH` (customer → API, from CRM/usage data), `ACCOUNT_MANAGER_OF`
- work: `AUTHORED`, `REVIEWED`, `TOUCHES` (PR → service), `FIXES`, `ASSIGNED_TO`, `REPORTED`, `ABOUT`, `FOR_CUSTOMER`, `PART_OF` (ticket → incident)
- talk: `POSTED`, `IN` (channel), `REPLY_TO`, `MENTIONS`, `ATTENDED`
- decisions: `DECIDED`, `DECIDED_IN`, `DOCUMENTED_IN`, `TRIGGERED_BY`, `AFFECTS`, `REJECTED` (alternatives), `IMPLEMENTED_BY`, `EVIDENCED_BY`, and at runtime `SUPERSEDES`, `UPDATES`, `CONFLICTS_WITH`
- docs: `STATES` (doc → claim), `CITES` (doc → doc), and at runtime `CONTRADICTED_BY` (claim → decision)
- derived: `COLLABORATES {weight, via}` (person ↔ person), computed in Cypher from reviews, threads, meetings, tickets and decisions
- agent: `FOR`, `TARGETS` (task), `CITES` (answer → source)

## Ingestion (seed)

`capybrain/seed.py`. Deterministic, no LLM, about 25 s on first run (embeddings), 1 s after that.

1. Structured exports (org chart, CRM, tickets, PRs, incidents) become nodes and edges as-is.
2. Free text (Slack, ticket and PR text, meeting notes, docs) is linked to entities with a **gazetteer**
   (`capybrain/linker.py`): aliases for people, services, APIs, customers and docs, plus patterns for keys like
   `SUP-298`, `INC-142`, `PR #881`, `ADR-007`.
3. Docs are split into **claims** (sentences, bullets, table rows). Claims are what can go stale later.
4. Decisions come from ADR and meeting-note front matter (who decided, where, what it affects, rejected options,
   evidence messages).
5. Every text gets a local embedding (`BAAI/bge-small-en-v1.5` via fastembed, 384 dims) for the vector index.
6. The collaboration graph is derived with Cypher (code review pairs, thread replies, shared meetings, ...).
7. The finished graph is stored as `tallybird_seed`; the live graph `tallybird` is a `GRAPH.COPY` of it.
   "Reset demo" is just another `GRAPH.COPY`.

Why a gazetteer and not an LLM for linking? It is instant, free, deterministic and testable; the LLM is used
where judgement is needed (is this message a decision? does this sentence contradict it?).

## Ask: the agent loop

`capybrain/agent.py` streams events to the UI over SSE.

- The model (Qwen3.8-27B on W&B Inference by default; any OpenAI-compatible endpoint with tool calling works)
  gets seven tools: `trace_decision`, `who_knows`, `impact_of`, `open_work`, `search`, `get_details`,
  `graph_query`.
- Each tool runs named Cypher queries from `capybrain/queries.py` and returns three things: compact JSON for the
  model (with cite keys S1, S2, ...), the nodes and relationships it walked (the UI lights them up), and the
  Cypher it ran (shown in the trace).
- The model must cite sources as `[S3]`. The UI turns those into chips that open the original message, doc,
  meeting or ticket.
- `graph_query` lets the model write its own Cypher for odd questions, but it runs through `GRAPH.RO_QUERY`, so
  FalkorDB itself refuses writes (and a regex guard rejects them earlier).
- **Memory:** every answer is stored as an `Answer` node with `CITES` edges and an embedding. When a similar
  question comes back, Capy recalls the old answer and checks whether any cited source has since become
  stale or superseded.

### How "who knows X" is scored (`expertise` query)
`3 × PRs authored + 2 × PRs reviewed + 1.5 × messages mentioning X + 2 × docs about X + 1 × meetings about X
+ 1 × decisions affecting X + 1 × tickets about X assigned to them + 5 if they own X`. People whose `status`
is `departed` are reported separately as "left the company", never as someone to ask.

## A change lands: the ripple pipeline

`capybrain/ripple.py`, about 15–20 s end to end with the three LLM calls running in parallel.

1. **Message**: written as a `Message` node, linked to author, channel and mentioned entities.
2. **Extraction** (LLM, JSON, thinking off): is it a decision? title, summary, effective date, what it affects
   (only what changes or breaks, not migration targets). Names are resolved to graph nodes.
3. **Decision node**: `Decision` with `EVIDENCED_BY` the message, `DECIDED` by the author, `AFFECTS` the
   resolved entities.
4. **Impact** (pure Cypher): services that expose, call, authenticate or depend on the affected thing (up to
   three hops), integrated customers and their account managers, active decisions and promises, docs with claims
   about it, open tickets. The UI shows it as rings.
5. **Three judges in parallel** (LLM):
   - *conflicts*: the new decision vs. earlier active decisions affecting the same entities → `SUPERSEDES`,
     `UPDATES` or `CONFLICTS_WITH`. Thinking is on here because this is the judgement call (it catches that a
     Dec 1 sunset breaks ADR-011's 60-days-notice promise).
   - *stale claims*: candidate claims come from the graph (claims `ABOUT` the affected entities) plus the vector
     index (claims similar in meaning), batched 5 at a time. Contradicted claims get `status: 'stale'`, a
     rewrite, and `CONTRADICTED_BY` the decision; their doc becomes stale. ADRs and postmortems are skipped
     (historical records are superseded, not edited).
   - *customer notices*: short drafts per integrated customer; customers with a conflicting promise get a
     "resolve conflict" task instead of an email.
6. **Proposals**: each follow-up is routed through the graph. Doc fixes go to the doc's author, or, if every
   author has left, to whoever the `expertise` query ranks highest for what the doc is about. Service changes
   go to the owner, or to the best active expert if the owner left. Customer notices go to the account
   manager. Conflicts go to the people who made the earlier decision.
7. **Approve**: writes `Task` nodes (`FOR` the decision, `ASSIGNED_TO` a person, `TARGETS` a doc, customer or
   service). After that, "what's left for the v1 sunset?" is answered from the graph.

## Org X-ray

- **Real working groups**: `algo.labelPropagation` over `COLLABORATES` edges between active people. Ties
  need weight ≥ 2.5 and are stored in both directions so the algorithm treats them as undirected. The seed is
  deterministic, so the groups are reproducible.
- **Hidden connectors**: `algo.betweenness` (fixed `samplingSeed` for reproducibility).
- **Docs everything builds on**: `algo.pageRank('Doc', 'CITES')`. The two most-cited docs are the two that
  go stale.
- **Knowledge at risk**: per service, the share of PR authorship and review done by people who left, and
  whether the owner left.

## Why the graph is not decoration

- Every answer is computed by Cypher over relationships. The vector index only picks starting points.
- `tests/test_graph.py::test_graph_is_not_decoration_ablation` deletes the `INTEGRATES_WITH` relationships in
  a copy of the graph (every node and every text stays): "which customers break if v1 goes away" goes from 3
  customers to 0.
- Side by side in the UI: plain vector RAG over the same text, same model, finds one customer and says it
  can't see the rest; the graph finds all three, their account managers and the promise to Orchard Health.
- Ownership, "who has left", customer integrations, decision lineage and staleness are all relationships or
  properties on relationships. None of that exists in text chunks.

## FalkorDB features used

Vector index (`db.idx.vector.queryNodes`) on 4 labels, full-text index (`db.idx.fulltext.queryNodes`, incl.
fuzzy `%term%`), range indexes, variable-length paths, pattern comprehensions, `UNION`, `algo.labelPropagation`,
`algo.betweenness`, `algo.pageRank`, `GRAPH.COPY` (seed / reset / ablation copies), `GRAPH.RO_QUERY` (agent
Cypher sandbox), multiple graphs per instance (seed, live, tests).

## Questions judges are likely to ask

- **Is the data real?** No. Tallybird is fictional and the dataset was written for the demo (see
  `data/tallybird/`). It is shaped like real exports so the same pipeline would take real Slack/Jira/GitHub data.
- **What does the LLM do vs. the graph?** The LLM picks tools, reads results and writes; it judges conflicts
  and staleness. The graph does retrieval, ownership, impact, expertise ranking and routing. Every fact in an
  answer comes from a tool result.
- **What if the LLM is wrong about a conflict?** Nothing changes for people until a human approves the
  proposals. The reasons are shown next to each relation and task.
- **Why Qwen on W&B instead of a frontier model?** It is what we had credits for; the code uses the standard
  OpenAI-compatible API, so swapping models is one environment variable.
- **How would this scale?** Ingestion is incremental (the ripple pipeline is the incremental path). FalkorDB
  hosts one graph per tenant; queries here run in milliseconds on ~550 nodes / ~2,100 edges.
- **Why are ADRs never marked stale?** They are historical records. A newer decision supersedes them in the
  graph instead.

## Known limits (be upfront)

- The seed decision records are curated from ADR and meeting front matter; only live messages go through LLM
  extraction.
- Label propagation results depend on tie thresholds; we chose ≥ 2.5 and keep the seed deterministic.
- Customer notices and doc rewrites are drafts for a human to approve, not sent anywhere.
