---
title: "CapyBrain: a company brain that stays calm when things change"
subtitle: "How we built a FalkorDB-powered agent that answers with a path, notices when the company changes, and drafts the follow-up work"
tags: [falkordb, knowledge-graph, ai-agents, graphrag, hackathon]
---

# CapyBrain: a company brain that stays calm when things change

*Built for Graph Hacks 2026 (WeMakeDevs × FalkorDB), Company Brain track.*

Every company has a brain. It's just scattered across Slack threads, tickets, docs and people's heads, and the
moment someone leaves or a plan changes, part of it quietly goes out of date.

We built **CapyBrain**, a company brain on a FalkorDB graph, and gave it a mascot: **Capy**, a capybara soaking
in a hot spring with a yuzu on her head. Capybaras famously get along with everyone and never panic, which
happened to be exactly the product brief: *knows everyone, remembers why, stays calm when things change.*

## The problem with "chat with your docs"

Most company-knowledge tools are vector search over text chunks. That works for "what does the runbook say?"
and breaks down for the questions that matter:

- *Who can help with the ledger service?* The docs say "page Dana". Dana left in August.
- *Which customers break if we switch off API v1?* That fact lives in CRM integration records, not in prose.
- *We just decided X. What did that make wrong?* Text search can't tell you which promises and docs a decision
  contradicts.

All three answers are **relationships**: who owns what, who has left, which customer integrates with which API,
which decision affects which system, which doc states what. So we put the relationships first.

## The graph

Our fictional company, Tallybird, is a payments startup with 33 people, 15 services, 3 APIs, 12 customers, and a
realistic paper trail: a Slack export, tickets, PRs, ADRs, runbooks and meeting notes, about 540 nodes and 2,100
relationships in total.

The model is plain and explicit:

- `(Person)-[:OWNS {until}]->(Service)`, `(Service)-[:EXPOSES|CALLS|AUTHENTICATES]->(Api)`,
  `(Customer)-[:INTEGRATES_WITH]->(Api)`
- `(Person)-[:DECIDED]->(Decision)-[:DECIDED_IN]->(Meeting)`, `(Decision)-[:TRIGGERED_BY]->(Incident)`,
  `(Decision)-[:REJECTED]->(Alternative)`, `(Decision)-[:EVIDENCED_BY]->(Message)`
- `(Doc)-[:STATES]->(Claim)-[:ABOUT]->(Api)`: docs are split into individual statements, because statements,
  not whole docs, are what go stale
- `(Person)-[:COLLABORATES {weight}]->(Person)`, derived in Cypher from code reviews, threads and meetings

Ingestion is deterministic. Structured exports load as-is, a gazetteer links free text to entities (names,
aliases, `SUP-298`, `PR #881`, `ADR-007`), and every text gets a local embedding for FalkorDB's vector index.
No LLM is needed to seed the graph, so it's fast, free and testable.

## Answering with a path

Capy is an LLM tool loop (Qwen3.8-27B via W&B Inference) with seven tools. Each tool is a small set of named
Cypher queries and returns three things: data for the model, with citation keys; the nodes and relationships it
walked, which the UI lights up; and the Cypher it ran, which the UI shows on demand.

Ask *"why did we move webhooks to a queue?"* and the graph does the work. Vector search finds the decision, then
the trace query walks to the incident that triggered it, the architecture review, the people who decided, the
options they rejected, the Slack messages that argued it and the PRs that shipped it. The answer cites every
step.

Ask *"who can help with the ledger service?"* and an expertise query scores every person by evidence: PRs
authored and reviewed, messages, docs, meetings, tickets. People whose `status` is `departed` are reported as
"left the company", never as someone to ask. The answer: Marco, who reviewed most of Dana's ledger code, and Wei,
a support engineer who has quietly been answering ledger questions for months. The org chart would have said
"ask Tom", the manager, who has never changed its code.

We also run plain vector RAG over the same text, with the same model, side by side. On *"which customers break
if we switch off v1?"* it finds one customer and admits it can't see the rest. The graph finds all three, their
account managers, and a promise Sales made to one of them.

## When a change lands

This is the part we're proudest of. Paste a new message, *"we're switching off REST API v1 on December 1st"*, and
the **ripple pipeline** runs:

1. The message is written to the graph and linked to what it mentions.
2. The LLM extracts the decision (title, effective date, what it affects) and it becomes a `Decision` node.
3. Cypher walks out from REST API v1: 5 services, 3 customers, 2 earlier decisions, 4 open tickets.
4. Three LLM judges run in parallel over **graph-selected candidates**:
   - Earlier decisions affecting the same things. It catches that the sunset breaks a promise to Orchard Health,
     and that Dec 1 is only 46 days away when ADR-011 promised 60 days' notice.
   - Doc statements about v1, from the graph plus the vector index. Contradicted ones get `status: 'stale'`, a
     suggested rewrite, and a `CONTRADICTED_BY` edge. The API Quickstart turns red.
   - Draft customer notices.
5. Follow-up tasks are **routed through the graph**:
   - doc fixes go to their authors, or to the best active expert when every author has left
   - customer notices go to account managers
   - conflicts go to whoever made the earlier promise
   - the auth-service work goes to Marco, because its owner left

Approve, and the tasks become `Task` nodes. Tomorrow, *"what's left for the v1 sunset?"* has an answer.

The whole ripple takes about six seconds. An early version took 54. Two changes fixed it: running the judges in
parallel, and turning off the model's reasoning for the JSON calls while telling it explicitly to count the days
between dates when a notice period was promised. It was faster *and* it caught the 60-day conflict more reliably.

## Org X-ray

FalkorDB ships graph algorithms, so we pointed them at the collaboration graph:

- `algo.labelPropagation` finds real working groups. None of them matches the org chart, and the usage-billing
  squad spans Growth, Data and Payments.
- `algo.betweenness` finds the hidden connectors.
- `algo.pageRank` over doc citations shows that the two most-cited docs in the company are the two that go stale.

## Proving the graph isn't decoration

The rules say that if the product still works without FalkorDB, the graph is decoration. So we wrote a test for
it. Using `GRAPH.COPY`, we clone the graph, delete only the `INTEGRATES_WITH` relationships, keep every node and
every word of text, and ask which customers break if v1 goes away. The answer goes from 3 to 0.

Other FalkorDB features that made life easy:

- `GRAPH.COPY` is also our one-click demo reset.
- `GRAPH.RO_QUERY` lets the model write its own Cypher for odd questions while the database refuses any write.
- Vector and full-text indexes live next to the graph, so one query can go from "find me something like this" to
  "now walk three hops".

## What we learned

- **Put judgement where it's needed, and only there.** The graph does retrieval, ownership, impact and routing.
  The LLM decides whether a sentence contradicts a decision. Splitting it that way made the system fast,
  explainable and testable.
- **Statements go stale, not documents.** Splitting docs into claims made "what did this decision make wrong?" a
  graph question.
- **"Who has left" is the most valuable property in a company graph.** Half the bad advice in a company comes from
  docs that point at people who are gone.

## Try it

- **Demo video (3 min):** https://www.youtube.com/watch?v=e1h5JVlbJRE
- **Code:** https://github.com/chinesepowered/hack-falkor (README, full Cypher catalog, ablation test)
- **Run it:** `docker compose up --build`, set an OpenAI-compatible LLM key, and open http://localhost:8000.

*Built with heavy help from Claude Code. Tallybird and everyone in it are fictional. Capy is very calm about it.*
