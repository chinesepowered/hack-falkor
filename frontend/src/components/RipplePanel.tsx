import { useState } from 'react';
import type { ConflictItem, GNode, PresetEvent, StaleDoc } from '../types';
import Capy from './Capy';

export interface RippleState {
  running: boolean;
  step: number; // 0 idle, 1 message, 2 extracted, 3 impact, 4 conflicts, 5 stale, 6 proposals, 7 done
  startedAt?: number;
  times: Record<number, number>;
  message?: GNode;
  extraction?: { title: string; summary: string; effective_date?: string | null; affects?: string[] };
  affects?: GNode[];
  decision?: GNode;
  counts?: Record<string, number>;
  conflicts?: ConflictItem[];
  stale?: StaleDoc[];
  checked?: number;
  proposals?: number;
  error?: string;
  note?: string;
  seconds?: number;
}

export const EMPTY_RIPPLE: RippleState = { running: false, step: 0, times: {} };

const REL_CLASS: Record<string, string> = { conflicts: 'bad', supersedes: 'muted', updates: 'warn' };

export default function RipplePanel({ events, state, onInject, onOpen }: {
  events: PresetEvent[];
  state: RippleState;
  onInject: (ev: PresetEvent, text: string) => void;
  onOpen: (id: string) => void;
}) {
  const [sel, setSel] = useState<string>(events[0]?.id || '');
  const [texts, setTexts] = useState<Record<string, string>>({});
  const current = events.find((e) => e.id === sel) || events[0];
  const mood = state.error ? 'alert' : state.running ? 'thinking' : state.step >= 7 ? 'happy' : 'idle';
  const t = (k: number) => (state.times[k] && state.startedAt ? `${((state.times[k] - state.startedAt) / 1000).toFixed(1)}s` : '');

  const Step = ({ n, title, children }: { n: number; title: string; children?: React.ReactNode }) => {
    const done = state.step >= n;
    const active = state.running && state.step === n - 1;
    return (
      <div className={`tl-step ${done ? 'done' : ''} ${active ? 'active' : ''}`}>
        <div className="tl-dot">{done ? '✓' : active ? <span className="spin" /> : n}</div>
        <div className="tl-body">
          <div className="tl-title">{title}<span className="tl-time">{t(n)}</span></div>
          {done && children}
        </div>
      </div>
    );
  };

  return (
    <div className="panel ripple">
      <div className="scroll">
        <div className="ripple-hero">
          <Capy mood={mood} size={120} bath />
          <div>
            <h2>A change lands.</h2>
            <p>Drop a new message into the company. Capy updates the graph, works out what just went stale, and drafts the follow-up work.</p>
          </div>
        </div>

        {state.step === 0 && (
          <div className="events">
            {events.map((e) => (
              <button key={e.id} className={`event ${sel === e.id ? 'sel' : ''}`} onClick={() => setSel(e.id)}>
                <span className="ev-author">{e.author_name} <span className="muted">in #{e.channel.split(':')[1]}</span></span>
                <span className="ev-label">{e.label}</span>
              </button>
            ))}
            {current && (
              <div className="compose">
                <div className="slack-msg">
                  <div className="avatar-initial">{current.author_name[0]}</div>
                  <div>
                    <b>{current.author_name}</b> <span className="muted">#{current.channel.split(':')[1]} · today 09:30</span>
                    <textarea value={texts[current.id] ?? current.text} rows={3}
                      onChange={(ev) => setTexts({ ...texts, [current.id]: ev.target.value })} />
                  </div>
                </div>
                <button className="primary big" onClick={() => onInject(current, texts[current.id] ?? current.text)}>
                  Drop it in the hot spring 🍊
                </button>
              </div>
            )}
          </div>
        )}

        {state.step > 0 && (
          <div className="timeline">
            <Step n={1} title="Message written to the graph">
              {state.message && <div className="quote">“{String(state.message.text || state.message.name)}”</div>}
            </Step>
            <Step n={2} title="Capy reads it">
              {state.extraction && (
                <div className="extract">
                  <div><b>{state.decision?.name || state.extraction.title}</b></div>
                  {state.extraction.effective_date && <div className="muted">effective {state.extraction.effective_date}</div>}
                  <div className="chips-row">{(state.affects || []).map((a) => <span key={a.id} className="mini-chip">affects {a.name}</span>)}</div>
                </div>
              )}
              {state.note && <div className="muted">{state.note}</div>}
            </Step>
            <Step n={3} title="Ripple through the graph">
              {state.counts && (
                <div className="counts">
                  <span><b>{state.counts.services}</b> services</span>
                  <span><b>{state.counts.customers}</b> customers</span>
                  <span><b>{state.counts.decisions}</b> earlier decisions</span>
                  <span><b>{state.counts.tickets}</b> open tickets</span>
                </div>
              )}
            </Step>
            <Step n={4} title="Checked against earlier decisions">
              {(state.conflicts || []).length === 0 && <div className="muted">No tension with earlier decisions.</div>}
              {(state.conflicts || []).map((c) => (
                <button key={c.id} className="conflict" onClick={() => onOpen(c.id)}>
                  <span className={`rel ${REL_CLASS[c.relation] || ''}`}>{c.relation}</span>
                  <span><b>{c.decision}</b><br /><span className="muted">{c.reason}</span></span>
                </button>
              ))}
            </Step>
            <Step n={5} title={`Docs that just went stale${state.checked ? ` (${state.checked} statements checked)` : ''}`}>
              {(state.stale || []).map((d) => (
                <button key={d.doc.id} className="stale-doc" onClick={() => onOpen(d.doc.id)}>
                  📄 <b>{d.doc.name}</b> <span className="muted">· {d.claims.length} statement{d.claims.length > 1 ? 's' : ''}</span>
                </button>
              ))}
            </Step>
            <Step n={6} title="Follow-up work drafted">
              {state.proposals !== undefined && <div className="muted">{state.proposals} tasks proposed, each routed through the ownership graph. Review them on the right →</div>}
            </Step>
            {state.error && <div className="error">{state.error}</div>}
            {state.seconds !== undefined && <div className="meta">Whole ripple: {state.seconds}s</div>}
          </div>
        )}
      </div>
    </div>
  );
}
