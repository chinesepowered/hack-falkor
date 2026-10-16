"""The Cypher catalog: every graph query CapyBrain depends on, in one place.

`scripts/export_queries.py` renders this module into docs/queries.md, so the README's list
of queries is always the code that actually runs.
"""

Q: dict[str, dict] = {}


def q(name: str, purpose: str, cypher: str) -> str:
    Q[name] = {"purpose": purpose, "cypher": cypher.strip()}
    return Q[name]["cypher"]


# --------------------------------------------------------------------------- retrieval
VECTOR_SEARCH = q("vector_search", "Semantic entry points: nearest Searchable nodes (messages, docs, claims, tickets, PRs, meetings, decisions, incidents) to the question embedding.", """
CALL db.idx.vector.queryNodes('Searchable', 'embedding', $k, vecf32($vec)) YIELD node, score
RETURN node, score
ORDER BY score ASC
""")

DECISION_SEARCH = q("decision_search", "Find the decisions closest in meaning to a topic (vector index on Decision.embedding).", """
CALL db.idx.vector.queryNodes('Decision', 'embedding', $k, vecf32($vec)) YIELD node, score
RETURN node, score
ORDER BY score ASC
""")

CLAIM_SEARCH = q("claim_search", "Find doc statements closest in meaning to a new decision (vector index on Claim.embedding), with their doc.", """
CALL db.idx.vector.queryNodes('Claim', 'embedding', $k, vecf32($vec)) YIELD node, score
MATCH (d:Doc)-[:STATES]->(node)
RETURN node, d, score
ORDER BY score ASC
""")

ANSWER_SEARCH = q("answer_search", "Agent memory: earlier answers closest to a new question, with the sources they cited and whether any of those sources has since gone stale or been superseded.", """
CALL db.idx.vector.queryNodes('Answer', 'embedding', $k, vecf32($vec)) YIELD node, score
OPTIONAL MATCH (node)-[:CITES]->(src:Entity)
RETURN node, score, collect(src) AS sources,
  size([s IN collect(src) WHERE s.status IN ['stale', 'superseded', 'departed']]) AS stale_sources
ORDER BY score ASC
""")

FULLTEXT_SEARCH = q("fulltext_search", "Keyword / fuzzy lookup of entities by name or alias (RediSearch full-text index on Entity.name and Entity.aka).", """
CALL db.idx.fulltext.queryNodes('Entity', $q) YIELD node, score
RETURN node, score
ORDER BY score DESC
LIMIT $k
""")

NODE_BY_ID = q("node_by_id", "Fetch one node by its stable id.", """
MATCH (n:Entity {id: $id}) RETURN n
""")

NEIGHBOURS = q("neighbours", "One-hop neighbourhood of a node, used by the source panel and the agent's get_details tool.", """
MATCH (n:Entity {id: $id})-[r]-(m:Entity)
WHERE NOT m:Claim
RETURN type(r) AS rel, startNode(r).id = n.id AS outgoing, m
LIMIT $limit
""")

THREAD = q("thread", "A Slack thread: the root message and every reply, with authors, in time order.", """
MATCH (root:Message {id: $root})
OPTIONAL MATCH (reply:Message)-[:REPLY_TO]->(root)
WITH root, collect(reply) AS replies
UNWIND [root] + replies AS m
MATCH (author:Person)-[:POSTED]->(m)
RETURN m, author
ORDER BY m.ts
""")

# --------------------------------------------------------------------------- decisions
DECISION_CORE = q("decision_trace", "Why was a decision made? Who made it, where, what triggered it, which alternatives were rejected, how it was implemented, and the messages that are its evidence.", """
MATCH (d:Decision {id: $id})
RETURN d,
  [(d)-[:DECIDED_IN]->(m:Meeting) | m] AS meetings,
  [(p:Person)-[:DECIDED]->(d) | p] AS deciders,
  [(d)-[:TRIGGERED_BY]->(i:Incident) | i] AS triggers,
  [(d)-[:DOCUMENTED_IN]->(doc:Doc) | doc] AS docs,
  [(d)-[:REJECTED]->(a:Alternative) | a] AS rejected,
  [(d)-[:IMPLEMENTED_BY]->(pr:PR) | pr] AS prs,
  [(d)-[:EVIDENCED_BY]->(msg:Message) | msg] AS evidence,
  [(d)-[:AFFECTS]->(x:Entity) | x] AS affects,
  [(d)-[:SUPERSEDES]->(old:Decision) | old] AS supersedes,
  [(newer:Decision)-[:SUPERSEDES]->(d) | newer] AS superseded_by,
  [(d)-[:CONFLICTS_WITH]-(c:Decision) | c] AS conflicts
""")

DECISION_EVIDENCE_AUTHORS = q("evidence_authors", "Authors of the evidence messages behind a decision.", """
MATCH (d:Decision {id: $id})-[:EVIDENCED_BY]->(m:Message)<-[:POSTED]-(p:Person)
RETURN m.id AS message, p
""")

INCIDENT_THREAD = q("incident_thread", "The chat thread where an incident was first discussed: messages that mention the incident or its tickets.", """
MATCH (:Incident {id: $id})<-[:MENTIONS]-(m:Message)
RETURN m
UNION
MATCH (:Incident {id: $id})<-[:PART_OF]-(:Ticket)<-[:MENTIONS]-(m:Message)
RETURN m
""")

# --------------------------------------------------------------------------- people
EXPERTISE = q("expertise", "Who knows X? Score every person by evidence in the graph: PRs authored or reviewed that touch X, messages that mention X, docs about X, meetings about X, decisions affecting X and tickets about X. Ownership (and whether the owner has left) comes from OWNS edges.", """
MATCH (x:Entity {id: $id})
MATCH (p:Person)
WITH x, p,
  size([(p)-[:AUTHORED]->(pr1:PR)-[:TOUCHES]->(x) | pr1]) AS authored,
  size([(p)-[:REVIEWED]->(pr2:PR)-[:TOUCHES]->(x) | pr2]) AS reviewed,
  size([(p)-[:POSTED]->(m1:Message)-[:MENTIONS]->(x) | m1]) AS discussed,
  size([(p)-[:AUTHORED]->(d1:Doc)-[:ABOUT]->(x) | d1]) AS docs,
  size([(p)-[:ATTENDED]->(mt1:Meeting)-[:ABOUT]->(x) | mt1]) AS meetings,
  size([(p)-[:DECIDED]->(dc1:Decision)-[:AFFECTS]->(x) | dc1]) AS decisions,
  size([(x)<-[:ABOUT]-(t1:Ticket)-[:ASSIGNED_TO]->(p) | t1]) AS tickets,
  [(p)-[o1:OWNS]->(x) | o1.until] AS owned
WITH p, authored, reviewed, discussed, docs, meetings, decisions, tickets, owned,
  3.0 * authored + 2.0 * reviewed + 1.5 * discussed + 2.0 * docs + 1.0 * meetings + 1.0 * decisions + 1.0 * tickets
  + CASE WHEN size(owned) > 0 THEN 5.0 ELSE 0.0 END AS score
WHERE score > 0
MATCH (p)-[:MEMBER_OF]->(t:Team)
RETURN p, t.name AS team, score, authored, reviewed, discussed, docs, meetings, decisions, tickets, owned
ORDER BY score DESC
LIMIT $limit
""")

EXPERTISE_EVIDENCE = q("expertise_evidence", "Concrete items behind a person's expertise score (to cite them).", """
MATCH (p:Person {id: $person}), (x:Entity {id: $id})
OPTIONAL MATCH (p)-[r:AUTHORED|REVIEWED|POSTED]->(e)-[:TOUCHES|MENTIONS|ABOUT]->(x)
WITH p, x, e, type(r) AS how
WHERE e IS NOT NULL
RETURN DISTINCT e, how
ORDER BY e.at DESC
LIMIT $limit
""")

OWNERS = q("owners", "Current and former owners of a service (team and person), with the date ownership ended.", """
MATCH (s:Entity {id: $id})
OPTIONAL MATCH (team:Team)-[:OWNS]->(s)
OPTIONAL MATCH (p:Person)-[o:OWNS]->(s)
RETURN team, p, o.until AS until
""")

# --------------------------------------------------------------------------- impact
IMPACT_SERVICES = q("impact_services", "Services that would feel a change to X: services that expose, call or authenticate an API, or that depend on a service (up to 3 hops downstream).", """
MATCH path = (s:Service)-[:EXPOSES|CALLS|AUTHENTICATES|DEPENDS_ON*1..3]->(x:Entity {id: $id})
WITH s, path ORDER BY length(path)
WITH s, collect(path)[0] AS shortest
OPTIONAL MATCH (owner:Person)-[o:OWNS]->(s)
OPTIONAL MATCH (team:Team)-[:OWNS]->(s)
RETURN s, length(shortest) AS hops, type(relationships(shortest)[0]) AS via,
  [n IN nodes(shortest) | n.id] AS path_ids, [r IN relationships(shortest) | type(r)] AS path_rels,
  owner, o.until AS owner_until, team
ORDER BY hops, s.name
""")

IMPACT_CUSTOMERS = q("impact_customers", "Customers integrated with X (an API) or with an API that X exposes, with their account managers and ARR.", """
MATCH (c:Customer)-[:INTEGRATES_WITH]->(api:Api {id: $id})
OPTIONAL MATCH (am:Person)-[:ACCOUNT_MANAGER_OF]->(c)
RETURN c, api, am
UNION
MATCH (:Service {id: $id})-[:EXPOSES]->(api:Api)<-[:INTEGRATES_WITH]-(c:Customer)
OPTIONAL MATCH (am:Person)-[:ACCOUNT_MANAGER_OF]->(c)
RETURN c, api, am
""")

IMPACT_CLAIMS = q("impact_claims", "Statements in docs that talk about X (candidates for going stale when X changes).", """
MATCH (x:Entity {id: $id})<-[:ABOUT]-(cl:Claim)<-[:STATES]-(d:Doc)
OPTIONAL MATCH (author:Person)-[:AUTHORED]->(d)
RETURN cl, d, collect(DISTINCT author) AS authors
ORDER BY d.title, cl.ord
""")

IMPACT_DECISIONS = q("impact_decisions", "Active decisions (and promises) that affect X.", """
MATCH (dec:Decision)-[:AFFECTS]->(x:Entity {id: $id})
WHERE dec.status = 'active'
OPTIONAL MATCH (p:Person)-[:DECIDED]->(dec)
RETURN dec, collect(DISTINCT p) AS deciders
ORDER BY dec.at
""")

IMPACT_TICKETS = q("impact_tickets", "Open tickets about or mentioning X.", """
MATCH (t:Ticket)-[:ABOUT|MENTIONS|FOR_CUSTOMER]->(x:Entity {id: $id})
WHERE t.status <> 'done'
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(p:Person)
RETURN DISTINCT t, p
ORDER BY t.created DESC
""")

# --------------------------------------------------------------------------- work
OPEN_TASKS = q("open_tasks", "Follow-up tasks CapyBrain created for a decision (or any node), with assignees and status.", """
MATCH (t:Task)-[:FOR|TARGETS]->(x:Entity {id: $id})
OPTIONAL MATCH (t)-[:ASSIGNED_TO]->(p:Person)
OPTIONAL MATCH (t)-[:TARGETS]->(target:Entity)
RETURN DISTINCT t, p, collect(DISTINCT target) AS targets
ORDER BY t.status, t.created
""")

# --------------------------------------------------------------------------- org x-ray (graph algorithms)
COMMUNITIES = q("communities", "Real working groups: label propagation (CDLP) over the collaboration graph of active people.", """
CALL algo.labelPropagation({nodeLabels: ['Active'], relationshipTypes: ['COLLABORATES'], maxIterations: 20})
YIELD node, communityId
MATCH (node)-[:MEMBER_OF]->(t:Team)
RETURN communityId, collect({id: node.id, name: node.name, team: t.name}) AS members
ORDER BY size(members) DESC
""")

CONNECTORS = q("connectors", "Hidden connectors: betweenness centrality over the collaboration graph of active people.", """
CALL algo.betweenness({nodeLabels: ['Active'], relationshipTypes: ['COLLABORATES'], samplingSize: 64, samplingSeed: 42})
YIELD node, score
MATCH (node)-[:MEMBER_OF]->(t:Team)
RETURN node, t.name AS team, score
ORDER BY score DESC
LIMIT $limit
""")

KEY_DOCS = q("key_docs", "The docs everything else builds on: PageRank over the doc citation graph.", """
CALL algo.pageRank('Doc', 'CITES') YIELD node, score
RETURN node, score
ORDER BY score DESC
LIMIT $limit
""")

BUS_FACTOR = q("bus_factor", "Knowledge concentration per service: who has changed it (authored or reviewed PRs), and how much of that knowledge belongs to people who have left.", """
MATCH (s:Service)
OPTIONAL MATCH (p:Person)-[:AUTHORED|REVIEWED]->(pr:PR)-[:TOUCHES]->(s)
WITH s, p, count(pr) AS n
WITH s, collect(CASE WHEN p IS NULL THEN NULL ELSE {id: p.id, name: p.name, status: p.status, n: n} END) AS people
OPTIONAL MATCH (owner:Person)-[o:OWNS]->(s)
RETURN s, people, owner, o.until AS owner_until
ORDER BY s.name
""")

ORPHANED_DOCS = q("orphaned_docs", "Docs whose every author has left the company.", """
MATCH (d:Doc)<-[:AUTHORED]-(a:Person)
WITH d, collect(a) AS authors
WHERE all(a IN authors WHERE a.status = 'departed')
RETURN d, authors
ORDER BY d.title
""")

# --------------------------------------------------------------------------- overview
OVERVIEW_NODES = q("overview_nodes", "Nodes drawn in the main graph view (people, teams, services, APIs, customers, decisions, docs, incidents, meetings, tasks).", """
MATCH (n:Entity)
WHERE n:Person OR n:Team OR n:Service OR n:Api OR n:Customer OR n:Decision OR n:Doc OR n:Incident OR n:Meeting OR n:Task
RETURN n
""")

OVERVIEW_EDGES = q("overview_edges", "Edges between the nodes of the main graph view.", """
MATCH (a:Entity)-[r]->(b:Entity)
WHERE (a:Person OR a:Team OR a:Service OR a:Api OR a:Customer OR a:Decision OR a:Doc OR a:Incident OR a:Meeting OR a:Task)
  AND (b:Person OR b:Team OR b:Service OR b:Api OR b:Customer OR b:Decision OR b:Doc OR b:Incident OR b:Meeting OR b:Task)
  AND NOT type(r) IN ['COLLABORATES', 'REPORTS_TO', 'MENTIONS']
RETURN a.id AS source, type(r) AS type, b.id AS target
""")

STATS = q("stats", "Counts per node label.", """
MATCH (n:Entity)
RETURN [l IN labels(n) WHERE NOT l IN ['Entity', 'Searchable', 'Active']][0] AS label, count(*) AS c
ORDER BY c DESC
""")
