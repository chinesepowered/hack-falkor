import { useCallback, useRef, useState } from 'react';
import type { GLink, GNode } from './types';

export const linkKey = (l: { source: string | GNode; target: string | GNode; type: string }) => {
  const s = typeof l.source === 'object' ? l.source.id : l.source;
  const t = typeof l.target === 'object' ? l.target.id : l.target;
  return `${s}|${l.type}|${t}`;
};

const idOf = (v: string | GNode) => (typeof v === 'object' ? v.id : v);

/**
 * Holds the graph shown on the canvas. Node objects are kept stable (force-graph stores positions on
 * them), new nodes are placed next to a neighbour so evidence "grows out" of the graph instead of
 * flying in from the centre.
 */
export function useGraphStore() {
  const nodes = useRef(new Map<string, GNode>());
  const links = useRef(new Map<string, GLink>());
  const [data, setData] = useState<{ nodes: GNode[]; links: GLink[] }>({ nodes: [], links: [] });

  const publish = useCallback(() => {
    setData({ nodes: [...nodes.current.values()], links: [...links.current.values()] });
  }, []);

  const merge = useCallback((newNodes: GNode[] = [], newLinks: GLink[] = []) => {
    let changed = false;
    const fresh: GNode[] = [];
    for (const n of newNodes) {
      if (!n || !n.id) continue;
      const existing = nodes.current.get(n.id);
      if (existing) {
        const { x, y, vx, vy, ...rest } = n;
        void x; void y; void vx; void vy;
        Object.assign(existing, rest);
      } else {
        const copy = { ...n };
        nodes.current.set(n.id, copy);
        fresh.push(copy);
        changed = true;
      }
    }
    for (const l of newLinks) {
      const s = idOf(l.source), t = idOf(l.target);
      if (!nodes.current.has(s) || !nodes.current.has(t) || s === t) continue;
      const key = linkKey(l);
      if (links.current.has(key)) continue;
      links.current.set(key, { source: s, target: t, type: l.type, weight: l.weight });
      changed = true;
    }
    // place new nodes next to an already-positioned neighbour
    for (const n of fresh) {
      if (n.x !== undefined) continue;
      for (const l of newLinks) {
        const s = idOf(l.source), t = idOf(l.target);
        const other = s === n.id ? nodes.current.get(t) : t === n.id ? nodes.current.get(s) : undefined;
        if (other && other.x !== undefined && other.y !== undefined) {
          n.x = other.x + (Math.random() - 0.5) * 30;
          n.y = other.y + (Math.random() - 0.5) * 30;
          break;
        }
      }
    }
    if (changed) publish();
    return changed;
  }, [publish]);

  const load = useCallback((newNodes: GNode[], newLinks: GLink[]) => {
    nodes.current = new Map();
    links.current = new Map();
    merge(newNodes, newLinks);
    publish();
  }, [merge, publish]);

  const patch = useCallback((id: string, fields: Partial<GNode>) => {
    const n = nodes.current.get(id);
    if (n) Object.assign(n, fields);
  }, []);

  const get = useCallback((id: string) => nodes.current.get(id), []);

  return { data, merge, load, patch, get };
}
