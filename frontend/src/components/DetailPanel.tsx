import { useEffect, useState } from 'react';
import { api } from '../api';
import type { Source } from '../types';
import { TYPE_COLOR, TYPE_ICON, TYPE_LABEL, nodeLabel } from '../theme';
import Markdown from './Markdown';

export function TypeBadge({ type }: { type: string }) {
  return (
    <span className="type-badge" style={{ background: TYPE_COLOR[type] || '#ccc' }}>
      {TYPE_ICON[type] || '•'} {TYPE_LABEL[type] || type}
    </span>
  );
}

export function NodeDetail({ id, onOpen, onClose }: { id: string; onOpen: (id: string) => void; onClose: () => void }) {
  const [d, setD] = useState<any>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => {
    setD(null);
    setErr(null);
    api.node(id).then(setD).catch((e) => setErr(String(e)));
  }, [id]);
  if (err) return <div className="detail"><button className="close" onClick={onClose}>×</button><div className="error">{err}</div></div>;
  if (!d) return <div className="detail"><div className="status">Loading…</div></div>;
  const n = d.node;
  const groups: Record<string, any[]> = {};
  for (const x of d.neighbours) {
    const key = `${x.outgoing ? '' : '← '}${x.rel.replaceAll('_', ' ').toLowerCase()}${x.outgoing ? ' →' : ''}`;
    (groups[key] ||= []).push(x.node);
  }
  return (
    <div className="detail">
      <button className="close" onClick={onClose} title="Close">×</button>
      <TypeBadge type={n.type} />
      <h3>{nodeLabel(n)}</h3>
      <div className="facts">
        {n.title && n.type === 'Person' && <span>{n.title}</span>}
        {n.status && <span className={`status-pill ${n.status}`}>{n.status === 'departed' ? `left ${n.left}` : n.status}</span>}
        {(n.at || n.ts) && <span>{String(n.ts || n.at).slice(0, 16).replace('T', ' ')}</span>}
        {n.channel && <span>{n.channel}</span>}
        {n.arr && <span>${Number(n.arr).toLocaleString()} ARR</span>}
        {n.priority && <span>{n.priority}</span>}
        {n.kind && <span>{n.kind}</span>}
      </div>
      {n.summary && n.type === 'Decision' && <p className="summary">{n.summary}</p>}
      {d.thread && (
        <div className="thread">
          {d.thread.map((m: any) => (
            <div key={m.node.id} className={`msg ${m.node.id === id ? 'me' : ''}`}>
              <b>{m.author}</b> <span className="when">{String(m.node.ts || '').slice(5, 16).replace('T', ' ')}</span>
              <div>{m.text}</div>
            </div>
          ))}
        </div>
      )}
      {d.claims && d.claims.some((c: any) => c.status === 'stale') && (
        <div className="stale-box">
          <b>Out of date since a newer decision</b>
          {d.claims.filter((c: any) => c.status === 'stale').map((c: any) => (
            <div key={c.id} className="diff">
              <div className="del">− {c.text}</div>
              <div className="add">+ {c.rewrite}</div>
              <div className="why">{c.why}</div>
            </div>
          ))}
        </div>
      )}
      {n.text && !d.thread && n.type !== 'Decision' && (
        <div className="doc-text"><Markdown text={String(n.text).replace(/^# .*\n/, '')} /></div>
      )}
      {n.because && <p className="summary"><b>Why:</b> {n.because}</p>}
      {n.draft && <pre className="draft">{n.draft}</pre>}
      <div className="neigh">
        {Object.entries(groups).map(([rel, items]) => (
          <div key={rel} className="neigh-group">
            <div className="rel">{rel}</div>
            {items.slice(0, 12).map((m) => (
              <button key={m.id} className="neigh-item" onClick={() => onOpen(m.id)}>
                <i style={{ background: TYPE_COLOR[m.type] }} />
                {nodeLabel(m)}
                {m.status === 'departed' && <em> (left)</em>}
                {m.status === 'stale' && <em> (stale)</em>}
              </button>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}

export function SourcesList({ sources, cited, active, onOpen }: { sources: Source[]; cited: string[]; active?: string; onOpen: (s: Source) => void }) {
  const citedSet = new Set(cited);
  const list = sources.filter((s) => citedSet.has(s.key));
  if (!list.length) return null;
  return (
    <div className="sources">
      <h4>Sources this answer walked through</h4>
      {list.map((s) => (
        <button key={s.key} className={`source ${active === s.key ? 'active' : ''}`} onClick={() => onOpen(s)}>
          <span className="key">{s.key.slice(1)}</span>
          <span className="src-body">
            <span className="src-head"><TypeBadge type={s.type} /> <span className="when">{s.at}</span></span>
            <span className="src-title">{s.title}</span>
            {s.snippet && <span className="src-snip">{s.snippet}</span>}
          </span>
        </button>
      ))}
    </div>
  );
}

export function BaselineCard({ data, loading }: { data: any; loading: boolean }) {
  return (
    <div className="baseline">
      <div className="baseline-head">
        <span className="tag">Without the graph</span>
        <span>Plain vector RAG · same model · top-8 text chunks</span>
      </div>
      {loading && <div className="status">Searching text chunks…</div>}
      {data && (
        <>
          <Markdown text={data.answer.replace(/\[(\d+)\]/g, '⁽$1⁾')} />
          <div className="snips">
            {data.snippets.map((s: any) => (
              <span key={s.n} className="snip"><b>{s.n}</b> {s.type}: {String(s.title).slice(0, 60)}</span>
            ))}
          </div>
          <div className="meta">{data.seconds}s · no ownership, CRM, decision or who-has-left data</div>
        </>
      )}
    </div>
  );
}
