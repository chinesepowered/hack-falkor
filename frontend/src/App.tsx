import { useCallback, useEffect, useRef, useState } from 'react';
import { api, stream } from './api';
import { linkKey, useGraphStore } from './graphStore';
import type { ChatTurn, GLink, GNode, PresetEvent, Proposal } from './types';
import GraphView, { type Highlight, type Ripple } from './components/GraphView';
import AskPanel from './components/AskPanel';
import RipplePanel, { EMPTY_RIPPLE, type RippleState } from './components/RipplePanel';
import ProposalsPanel from './components/ProposalsPanel';
import XrayPanel from './components/XrayPanel';
import { BaselineCard, NodeDetail, SourcesList } from './components/DetailPanel';
import Capy from './components/Capy';

type Mode = 'ask' | 'ripple' | 'xray';
const emptyHl = (): Highlight => ({ nodes: new Set(), links: new Set() });
const LEFT_QUESTION = "What's left to do for the v1 sunset, and who's on it?";

export default function App() {
  const company = useGraphStore();
  const people = useGraphStore();
  const [mode, setMode] = useState<Mode>('ask');
  const [hl, setHl] = useState<Highlight>(emptyHl());
  const [ripple, setRipple] = useState<Ripple | null>(null);
  const [fitKey, setFitKey] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [turns, setTurns] = useState<ChatTurn[]>([]);
  const [busy, setBusy] = useState(false);
  const [compare, setCompare] = useState(false);
  const [baseline, setBaseline] = useState<{ loading: boolean; data: any } | null>(null);
  const [activeCite, setActiveCite] = useState<string | undefined>();
  const [events, setEvents] = useState<PresetEvent[]>([]);
  const [rip, setRip] = useState<RippleState>(EMPTY_RIPPLE);
  const [proposals, setProposals] = useState<Proposal[]>([]);
  const [decisionId, setDecisionId] = useState<string | undefined>();
  const [decisionName, setDecisionName] = useState<string | undefined>();
  const [approved, setApproved] = useState<number | null>(null);
  const [xray, setXray] = useState<any>(null);
  const [xrayView, setXrayView] = useState<'groups' | 'connectors'>('groups');
  const [health, setHealth] = useState<any>(null);
  const stepSets = useRef(new Map<string, { nodes: string[]; links: string[] }>());

  const refreshHealth = useCallback(() => api.health().then(setHealth).catch(() => setHealth(null)), []);

  const loadGraph = useCallback(async () => {
    const g = await api.graph();
    company.load(g.nodes, g.links);
    setFitKey((k) => k + 1);
  }, [company]);

  useEffect(() => {
    loadGraph();
    api.events().then(setEvents);
    refreshHealth();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (mode !== 'xray') return;
    setHl(emptyHl());
    setSelected(null);
    api.xray().then((d) => {
      setXray(d);
      people.load(d.graph.nodes, d.graph.links);
      setFitKey((k) => k + 1);
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  const light = (sets: { nodes: Set<string>; links: Set<string> }, nodes: GNode[] = [], links: GLink[] = [], focus?: string) => {
    nodes.forEach((n) => n && sets.nodes.add(n.id));
    links.forEach((l) => sets.links.add(linkKey(l)));
    setHl({ nodes: new Set(sets.nodes), links: new Set(sets.links), focus });
  };

  // ------------------------------------------------------------------ ask
  const ask = async (question: string) => {
    if (busy) return;
    setMode('ask');
    setBusy(true);
    setSelected(null);
    setActiveCite(undefined);
    setRipple(null);
    const id = `t${Date.now()}`;
    const history = turns.filter((t) => t.answer).flatMap((t) => [
      { role: 'user', content: t.question }, { role: 'assistant', content: t.answer }]);
    setTurns((ts) => [...ts, { id, question, reasoning: '', steps: [], answer: '', sources: [], cited: [], done: false }]);
    const update = (fn: (t: ChatTurn) => ChatTurn) => setTurns((ts) => ts.map((t) => (t.id === id ? fn(t) : t)));
    const sets = { nodes: new Set<string>(), links: new Set<string>() };
    setHl(emptyHl());
    if (compare) {
      setBaseline({ loading: true, data: null });
      api.baseline(question).then((d) => setBaseline({ loading: false, data: d })).catch(() => setBaseline(null));
    } else {
      setBaseline(null);
    }
    let reasoning = '';
    let lastPaint = 0;
    try {
      await stream('/api/ask', { question, history }, (ev) => {
        switch (ev.type) {
          case 'status':
            update((t) => ({ ...t, status: ev.text }));
            break;
          case 'memory':
            update((t) => ({ ...t, memory: ev }));
            break;
          case 'reasoning': {
            reasoning += ev.text;
            const now = Date.now();
            if (now - lastPaint > 180) {
              lastPaint = now;
              const tail = reasoning.replace(/\s+/g, ' ').trim().slice(-110);
              update((t) => ({ ...t, status: `💭 …${tail}` }));
            }
            break;
          }
          case 'answer_delta':
            update((t) => ({ ...t, answer: t.answer + ev.text }));
            break;
          case 'answer_reset':
            update((t) => ({ ...t, answer: '' }));
            break;
          case 'tool_call':
            update((t) => ({ ...t, status: undefined, steps: [...t.steps, { id: ev.id, name: ev.name, args: ev.args, done: false }] }));
            break;
          case 'tool_result':
            company.merge(ev.nodes, ev.links);
            light(sets, ev.nodes, ev.links);
            stepSets.current.set(`${id}:${ev.id}`, { nodes: ev.nodes.map((n: GNode) => n.id), links: ev.links.map(linkKey) });
            setFitKey((k) => k + 1);
            update((t) => ({ ...t, steps: t.steps.map((s) => (s.id === ev.id ? { ...s, done: true, summary: ev.summary, cypher: ev.cypher } : s)) }));
            break;
          case 'answer':
            update((t) => ({ ...t, answer: ev.text, sources: ev.sources, cited: ev.cited, seconds: ev.seconds, done: true }));
            break;
          case 'error':
            update((t) => ({ ...t, error: ev.message, done: true }));
            break;
        }
      });
    } catch (e) {
      update((t) => ({ ...t, error: String(e), done: true }));
    } finally {
      update((t) => ({ ...t, done: true }));
      setBusy(false);
    }
  };

  const openCite = (turnId: string, key: string) => {
    const t = turns.find((x) => x.id === turnId);
    const s = t?.sources.find((x) => x.key === key);
    if (!s) return;
    setActiveCite(key);
    setSelected(s.id);
    setHl((h) => ({ ...h, focus: s.id }));
  };

  const openStep = (turnId: string, stepId: string) => {
    const set = stepSets.current.get(`${turnId}:${stepId}`);
    if (!set) return;
    setHl({ nodes: new Set(set.nodes), links: new Set(set.links) });
    setFitKey((k) => k + 1);
  };

  const openNode = (nid: string) => {
    setSelected(nid);
    setHl((h) => ({ ...h, focus: nid }));
  };

  // ------------------------------------------------------------------ ripple
  const inject = async (ev: PresetEvent, text: string) => {
    setMode('ripple');
    setSelected(null);
    setProposals([]);
    setApproved(null);
    setDecisionId(undefined);
    const startedAt = Date.now();
    setRip({ running: true, step: 0, times: {}, startedAt });
    const sets = { nodes: new Set<string>(), links: new Set<string>() };
    setHl(emptyHl());
    const mark = (step: number) => setRip((r) => ({ ...r, step, times: { ...r.times, [step]: Date.now() } }));
    let origin = '';
    try {
      await stream('/api/ingest', { text, author: ev.author, channel: ev.channel, ts: ev.ts }, (e) => {
        switch (e.type) {
          case 'message':
            company.merge(e.nodes, e.links);
            light(sets, e.nodes, e.links, e.node.id);
            origin = e.node.id;
            setRipple({ origin, startedAt: Date.now() });
            setFitKey((k) => k + 1);
            setRip((r) => ({ ...r, message: { ...e.node, text } }));
            mark(1);
            break;
          case 'extracted':
            setRip((r) => ({ ...r, extraction: e.extraction, affects: e.affects }));
            break;
          case 'decision':
            company.merge(e.nodes, e.links);
            light(sets, e.nodes, e.links, e.node.id);
            origin = e.node.id;
            setDecisionId(e.node.id);
            setDecisionName(e.node.name);
            setRip((r) => ({ ...r, decision: e.node }));
            mark(2);
            break;
          case 'impact': {
            const all = e.rings.flatMap((r: any) => r.nodes);
            company.merge(all, e.links);
            setRipple({ origin, startedAt: Date.now() });
            e.rings.forEach((ring: any, i: number) => {
              setTimeout(() => {
                const ids = new Set(ring.nodes.map((n: GNode) => n.id));
                light(sets, ring.nodes, e.links.filter((l: any) => ids.has(l.source) || ids.has(l.target)), origin);
                if (i === e.rings.length - 1) setFitKey((k) => k + 1);
              }, 400 + i * 900);
            });
            setRip((r) => ({ ...r, counts: e.counts }));
            mark(3);
            break;
          }
          case 'conflicts':
            e.items.forEach((c: any) => c.relation === 'supersedes' && company.patch(c.id, { status: 'superseded' }));
            company.merge(e.nodes, e.links);
            light(sets, e.nodes, e.links, origin);
            setRip((r) => ({ ...r, conflicts: e.items }));
            mark(4);
            break;
          case 'stale':
            e.docs.forEach((d: any) => company.patch(d.doc.id, { status: 'stale' }));
            company.merge(e.nodes, e.links);
            light(sets, e.nodes, e.links, origin);
            setRip((r) => ({ ...r, stale: e.docs, checked: e.checked }));
            mark(5);
            break;
          case 'proposals':
            setProposals(e.items);
            setRip((r) => ({ ...r, proposals: e.items.length }));
            mark(6);
            break;
          case 'done':
            setRip((r) => ({ ...r, running: false, seconds: e.seconds, note: e.note, step: e.decision_id ? 7 : Math.max(r.step, 2) }));
            refreshHealth();
            break;
          case 'error':
            setRip((r) => ({ ...r, running: false, error: e.message }));
            break;
        }
      });
    } catch (err) {
      setRip((r) => ({ ...r, running: false, error: String(err) }));
    }
  };

  const approve = async (items: Proposal[]) => {
    if (!decisionId) return;
    const r = await api.approve(decisionId, items);
    company.merge(r.nodes, r.links);
    const ids = new Set<string>([decisionId, ...r.nodes.map((n) => n.id)]);
    r.links.forEach((l) => { ids.add(String(l.source)); ids.add(String(l.target)); });
    setHl({ nodes: ids, links: new Set(r.links.map(linkKey)), focus: decisionId });
    setRipple(null);
    setFitKey((k) => k + 1);
    setApproved(r.created);
    refreshHealth();
  };

  const reset = async () => {
    await api.reset();
    setTurns([]);
    setRip(EMPTY_RIPPLE);
    setProposals([]);
    setApproved(null);
    setDecisionId(undefined);
    setSelected(null);
    setHl(emptyHl());
    setRipple(null);
    setBaseline(null);
    setXray(null);
    await loadGraph();
    refreshHealth();
  };

  const lastTurn = turns[turns.length - 1];
  const graphData = mode === 'xray' ? people.data : company.data;
  const nodeCount = health ? Object.values(health.counts as Record<string, number>).reduce((a, b) => a + b, 0) : 0;

  return (
    <div className="app">
      <header>
        <div className="brand">
          <Capy mood="idle" size={44} />
          <div>
            <h1>CapyBrain</h1>
            <span className="sub">company brain for <b>Tallybird</b> <span className="fictional">fictional</span></span>
          </div>
        </div>
        <nav>
          <button className={mode === 'ask' ? 'on' : ''} onClick={() => setMode('ask')}>💬 Ask</button>
          <button className={mode === 'ripple' ? 'on' : ''} onClick={() => setMode('ripple')}>🌊 A change lands</button>
          <button className={mode === 'xray' ? 'on' : ''} onClick={() => setMode('xray')}>🩻 Org X-ray</button>
        </nav>
        <div className="stats">
          {health && <span>{nodeCount.toLocaleString()} nodes · {Number(health.edges).toLocaleString()} edges</span>}
          <span className="falkor">on FalkorDB</span>
          <button className="ghost" onClick={reset} title="Restore the seed graph (GRAPH.COPY)">Reset demo</button>
        </div>
      </header>
      <main>
        <section className="left">
          {mode === 'ask' && (
            <AskPanel turns={turns} busy={busy} compare={compare} onCompare={setCompare} onAsk={ask} onCite={openCite} onStep={openStep} />
          )}
          {mode === 'ripple' && <RipplePanel events={events} state={rip} onInject={inject} onOpen={openNode} />}
          {mode === 'xray' && <XrayPanel data={xray} view={xrayView} onView={setXrayView} onOpen={openNode} />}
        </section>
        <section className="center">
          <GraphView
            data={graphData}
            highlight={mode === 'xray' ? emptyHlStatic : hl}
            ripple={mode === 'ripple' ? ripple : null}
            colorBy={mode === 'xray' ? 'group' : 'type'}
            sizeBy={mode === 'xray' && xrayView === 'connectors' ? 'betweenness' : 'type'}
            legend={mode === 'xray' ? 'groups' : 'types'}
            labelAll={mode === 'xray'}
            fitKey={fitKey}
            onNodeClick={(n) => openNode(n.id)}
            onBackgroundClick={() => setHl((h) => ({ ...h, focus: undefined }))}
          />
          {mode === 'xray' && (
            <div className="graph-caption">Collaboration graph of active people · {xrayView === 'groups' ? 'colored by label propagation group' : 'sized by betweenness centrality'}</div>
          )}
        </section>
        <section className="right">
          {selected ? (
            <NodeDetail id={selected} onOpen={openNode} onClose={() => { setSelected(null); setActiveCite(undefined); }} />
          ) : mode === 'ask' ? (
            <div className="right-scroll">
              {compare && baseline && <BaselineCard data={baseline.data} loading={baseline.loading} />}
              {lastTurn && lastTurn.done && (
                <SourcesList sources={lastTurn.sources} cited={lastTurn.cited} active={activeCite}
                  onOpen={(s) => openCite(lastTurn.id, s.key)} />
              )}
              {!lastTurn && <Hint />}
            </div>
          ) : mode === 'ripple' ? (
            proposals.length ? (
              <div className="right-scroll">
                <ProposalsPanel decision={decisionName} items={proposals} approved={approved} onApprove={approve}
                  onAskLeft={() => ask(LEFT_QUESTION)} onOpen={openNode} />
              </div>
            ) : (
              <div className="right-scroll"><Hint ripple /></div>
            )
          ) : (
            <div className="right-scroll"><Hint xray /></div>
          )}
        </section>
      </main>
    </div>
  );
}

const emptyHlStatic: Highlight = { nodes: new Set(), links: new Set() };

function Hint({ ripple, xray }: { ripple?: boolean; xray?: boolean }) {
  return (
    <div className="hint">
      {ripple ? (
        <>
          <h4>How the ripple works</h4>
          <ol>
            <li>The message is written to the graph and linked to what it mentions.</li>
            <li>The LLM reads it; if it's a decision, a <b>Decision</b> node is created with its evidence.</li>
            <li>Cypher walks out from what it affects: services, customers, owners, docs, tickets.</li>
            <li>Earlier decisions and promises about the same things are checked for conflicts.</li>
            <li>Doc statements about it are checked; contradicted ones turn red.</li>
            <li>Follow-up tasks are drafted and routed through the ownership graph.</li>
          </ol>
        </>
      ) : xray ? (
        <>
          <h4>Org X-ray</h4>
          <p>The people graph is derived in Cypher from code reviews, shared threads, meetings and decisions. FalkorDB's <code>algo.labelPropagation</code>, <code>algo.betweenness</code> and <code>algo.pageRank</code> run on it directly.</p>
          <p>Click a person or a service to see the evidence.</p>
        </>
      ) : (
        <>
          <h4>Every answer is a path</h4>
          <p>Capy answers by calling tools that run Cypher on FalkorDB: vector and full-text search to find a starting point, then traversals across people, services, customers, decisions, docs, messages and tickets.</p>
          <p>The nodes and relationships it walks light up on the graph. Citations open the original message, doc or meeting.</p>
          <p className="muted">Tallybird and everyone in it are fictional.</p>
        </>
      )}
    </div>
  );
}
