import { useState } from 'react';
import { GROUP_COLORS } from '../theme';

function Cypher({ code }: { code: string }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button className="cy-toggle" onClick={() => setOpen(!open)}>{open ? 'hide' : 'show'} Cypher</button>
      {open && <div className="cypher"><pre>{code}</pre></div>}
    </>
  );
}

export default function XrayPanel({ data, view, onView, onOpen }: {
  data: any;
  view: 'groups' | 'connectors';
  onView: (v: 'groups' | 'connectors') => void;
  onOpen: (id: string) => void;
}) {
  if (!data) return <div className="panel"><div className="status">Running graph algorithms…</div></div>;
  const maxB = Math.max(1, ...data.connectors.map((c: any) => c.score));
  return (
    <div className="panel xray">
      <div className="scroll">
        <h2>Org X-ray</h2>
        <p className="muted">FalkorDB's built-in graph algorithms over who actually works with whom (code reviews, threads, meetings, decisions).</p>

        <div className="card">
          <div className="card-head">
            <h4>Real working groups</h4>
            <button className={`seg ${view === 'groups' ? 'on' : ''}`} onClick={() => onView('groups')}>color graph</button>
          </div>
          <p className="muted">Label propagation finds {data.communities.length} groups. None of them matches the org chart: each one spans several teams.</p>
          {data.communities.map((c: any, i: number) => (
            <div key={i} className="group">
              <span className="swatch" style={{ background: GROUP_COLORS[c.community % GROUP_COLORS.length] }} />
              <div>
                <div className="group-teams">{Object.keys(c.teams).join(' · ')}</div>
                <div className="group-members">
                  {c.members.map((m: any) => <button key={m.id} className="link" onClick={() => onOpen(m.id)}>{m.name.split(' ')[0]}</button>)}
                </div>
              </div>
            </div>
          ))}
          <Cypher code={data.cypher.communities} />
        </div>

        <div className="card">
          <div className="card-head">
            <h4>Hidden connectors</h4>
            <button className={`seg ${view === 'connectors' ? 'on' : ''}`} onClick={() => onView('connectors')}>size graph</button>
          </div>
          <p className="muted">Betweenness centrality: the people most paths between colleagues run through.</p>
          {data.connectors.map((c: any) => (
            <button key={c.id} className="bar-row" onClick={() => onOpen(c.id)}>
              <span className="bar-label">{c.name} <span className="muted">· {c.team}</span></span>
              <span className="bar"><i style={{ width: `${(100 * c.score) / maxB}%` }} /></span>
            </button>
          ))}
          <Cypher code={data.cypher.connectors} />
        </div>

        <div className="card">
          <h4>Knowledge at risk</h4>
          <p className="muted">Who has changed each service (PRs authored or reviewed), and how much of that knowledge left with people who quit.</p>
          {data.services.filter((s: any) => s.owner_left || s.share_by_departed > 0.2).map((s: any) => (
            <button key={s.id} className="risk-row" onClick={() => onOpen(s.id)}>
              <b>{s.name}</b>
              {s.owner_left && <span className="badge bad">owner left</span>}
              <span className="muted"> {Math.round(100 * s.share_by_departed)}% of changes by people who left · ask {s.top_active.slice(0, 2).join(', ') || 'nobody'}</span>
            </button>
          ))}
          <Cypher code={data.cypher.bus_factor} />
        </div>

        <div className="card">
          <h4>Docs everything builds on</h4>
          <p className="muted">PageRank over which docs cite which.</p>
          {data.key_docs.map((d: any, i: number) => (
            <button key={d.id} className="risk-row" onClick={() => onOpen(d.id)}>
              <span className="rank">{i + 1}</span> {d.name}
              {d.status === 'stale' && <span className="badge bad">stale</span>}
            </button>
          ))}
          <Cypher code={data.cypher.key_docs} />
        </div>

        <div className="card">
          <h4>Orphaned docs</h4>
          <p className="muted">Every author has left the company.</p>
          {data.orphaned_docs.map((d: any) => (
            <button key={d.id} className="risk-row" onClick={() => onOpen(d.id)}>
              📄 {d.name} <span className="muted">· {d.authors.join(', ')}</span>
            </button>
          ))}
          <Cypher code={data.cypher.orphaned_docs} />
        </div>
      </div>
    </div>
  );
}
