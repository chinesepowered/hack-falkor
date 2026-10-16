import { useEffect, useRef, useState } from 'react';
import type { ChatTurn } from '../types';
import { TOOL_LABEL } from '../theme';
import Capy from './Capy';
import Markdown from './Markdown';

export const SUGGESTIONS = [
  'Why did we move webhooks to a queue?',
  'Who can help me with the ledger service?',
  'Which customers would break if we switched off API v1, and who manages them?',
  "What's left to do for the v1 sunset, and who's on it?",
  'Which docs are out of date right now?',
];

interface Props {
  turns: ChatTurn[];
  busy: boolean;
  compare: boolean;
  onCompare: (v: boolean) => void;
  onAsk: (q: string) => void;
  onCite: (turnId: string, key: string) => void;
  onStep: (turnId: string, stepId: string) => void;
}

export default function AskPanel({ turns, busy, compare, onCompare, onAsk, onCite, onStep }: Props) {
  const [q, setQ] = useState('');
  const [openCypher, setOpenCypher] = useState<string | null>(null);
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => end.current?.scrollIntoView({ behavior: 'smooth', block: 'end' }), [turns]);

  const submit = (text: string) => {
    const t = text.trim();
    if (!t || busy) return;
    onAsk(t);
    setQ('');
  };

  return (
    <div className="panel ask">
      <div className="scroll">
        {turns.length === 0 && (
          <div className="welcome">
            <Capy mood="idle" size={150} bath />
            <h2>Hi, I'm Capy.</h2>
            <p>I know everyone at <b>Tallybird</b>, remember why things were decided, and stay calm when things change. Every answer is a path through the company graph.</p>
          </div>
        )}
        {turns.map((t) => (
          <div key={t.id} className="turn">
            <div className="q">{t.question}</div>
            <div className="a">
              <div className="avatar"><Capy mood={t.done ? (t.error ? 'alert' : 'happy') : 'thinking'} size={40} /></div>
              <div className="body">
                {t.memory && (
                  <div className={`memory ${t.memory.stale_sources.length ? 'stale' : ''}`}>
                    🧠 I answered this on {t.memory.at}.{' '}
                    {t.memory.stale_sources.length
                      ? `Since then ${t.memory.stale_sources.map((s) => s.name).join(', ')} changed, so I'm checking the graph again.`
                      : 'The sources still hold, but I re-checked the graph anyway.'}
                  </div>
                )}
                {t.steps.map((s) => (
                  <div key={s.id} className={`step ${s.done ? 'done' : 'running'}`}>
                    <button className="step-head" onClick={() => onStep(t.id, s.id)}>
                      <span className="spin" />
                      <span className="tool">{TOOL_LABEL[s.name] || s.name}</span>
                      <span className="args">{Object.values(s.args).map(String).join(', ').slice(0, 60)}</span>
                    </button>
                    {s.summary && <div className="sum">{s.summary}</div>}
                    {s.cypher && s.cypher.length > 0 && (
                      <>
                        <button className="cy-toggle" onClick={() => setOpenCypher(openCypher === s.id ? null : s.id)}>
                          {openCypher === s.id ? 'hide' : 'show'} Cypher ({s.cypher.length})
                        </button>
                        {openCypher === s.id && (
                          <div className="cypher">
                            {s.cypher.map((c, i) => (
                              <pre key={i}><span className="cy-name">// {c.name}</span>{'\n'}{c.cypher}</pre>
                            ))}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ))}
                {!t.done && !t.answer && <div className="status">{t.status || 'Capy is thinking…'}</div>}
                {t.answer && <Markdown text={t.answer} onCite={(k) => onCite(t.id, k)} cited={new Set(t.cited)} />}
                {t.error && <div className="error">{t.error}</div>}
                {t.done && t.seconds !== undefined && (
                  <div className="meta">{t.steps.length} graph {t.steps.length === 1 ? 'step' : 'steps'} · {t.cited.length} sources · {t.seconds}s</div>
                )}
              </div>
            </div>
          </div>
        ))}
        <div ref={end} />
      </div>
      <div className="composer">
        <div className="chips">
          {SUGGESTIONS.map((s) => (
            <button key={s} className="chip" disabled={busy} onClick={() => submit(s)}>{s}</button>
          ))}
        </div>
        <form onSubmit={(e) => { e.preventDefault(); submit(q); }}>
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Ask Capy about Tallybird…" disabled={busy} />
          <button type="submit" disabled={busy || !q.trim()}>Ask</button>
        </form>
        <label className="toggle">
          <input type="checkbox" checked={compare} onChange={(e) => onCompare(e.target.checked)} />
          <span>Compare with plain vector RAG (no graph)</span>
        </label>
      </div>
    </div>
  );
}
