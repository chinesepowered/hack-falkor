import { useEffect, useState } from 'react';
import type { Proposal } from '../types';

const KIND: Record<string, { icon: string; label: string }> = {
  resolve_conflict: { icon: '⚠️', label: 'Resolve conflicts' },
  service_change: { icon: '⚙️', label: 'Service changes' },
  doc_fix: { icon: '📄', label: 'Doc fixes' },
  customer_notice: { icon: '✉️', label: 'Customer notices' },
};

export default function ProposalsPanel({ decision, items, approved, onApprove, onAskLeft, onOpen }: {
  decision?: string;
  items: Proposal[];
  approved: number | null;
  onApprove: (items: Proposal[]) => void;
  onAskLeft: () => void;
  onOpen: (id: string) => void;
}) {
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => setChecked(Object.fromEntries(items.map((p) => [p.pid, true]))), [items]);
  const kinds = Object.keys(KIND).filter((k) => items.some((p) => p.kind === k));
  const selected = items.filter((p) => checked[p.pid]);

  return (
    <div className="proposals">
      <h3>Follow-up work</h3>
      <p className="muted">for <b>{decision}</b>. Each task is assigned through the graph: owners, account managers, doc authors, or whoever knows it best when the owner has left.</p>
      {kinds.map((k) => (
        <div key={k} className="prop-group">
          <div className="prop-kind">{KIND[k].icon} {KIND[k].label}</div>
          {items.filter((p) => p.kind === k).map((p) => (
            <div key={p.pid} className={`prop ${p.priority === 'high' ? 'high' : ''}`}>
              <label className="prop-head">
                <input type="checkbox" disabled={approved !== null} checked={!!checked[p.pid]}
                  onChange={(e) => setChecked({ ...checked, [p.pid]: e.target.checked })} />
                <span className="prop-title">{p.title}</span>
              </label>
              <div className="prop-meta">
                {p.assignee && (
                  <button className="assignee" onClick={() => onOpen(p.assignee!.id)}>
                    <span className="avatar-initial small">{String(p.assignee.name || '?')[0]}</span>{p.assignee.name}
                  </button>
                )}
                {p.priority === 'high' && <span className="prio">high</span>}
              </div>
              <div className="because">{p.because}</div>
              {p.draft && (
                <>
                  <button className="cy-toggle" onClick={() => setOpen(open === p.pid ? null : p.pid)}>
                    {open === p.pid ? 'hide draft' : p.kind === 'doc_fix' ? 'show suggested edits' : 'show draft'}
                  </button>
                  {open === p.pid && <pre className="draft">{p.draft}</pre>}
                </>
              )}
            </div>
          ))}
        </div>
      ))}
      <div className="prop-footer">
        {approved === null ? (
          <button className="primary big" disabled={!selected.length} onClick={() => onApprove(selected)}>
            Approve {selected.length} task{selected.length === 1 ? '' : 's'}
          </button>
        ) : (
          <>
            <div className="approved">✓ {approved} tasks written to the graph as Task nodes</div>
            <button className="primary" onClick={onAskLeft}>Ask Capy: what's left? →</button>
          </>
        )}
      </div>
    </div>
  );
}
