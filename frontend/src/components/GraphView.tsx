import { useEffect, useMemo, useRef, useState } from 'react';
import ForceGraph2D from 'react-force-graph-2d';
import type { GLink, GNode } from '../types';
import { GROUP_COLORS, TYPE_COLOR, TYPE_LABEL, TYPE_RADIUS, nodeLabel } from '../theme';
import { linkKey } from '../graphStore';

export interface Highlight {
  nodes: Set<string>;
  links: Set<string>;
  focus?: string;
}

export interface Ripple {
  origin: string;
  startedAt: number;
}

interface Props {
  data: { nodes: GNode[]; links: GLink[] };
  highlight: Highlight;
  ripple?: Ripple | null;
  colorBy?: 'type' | 'group';
  sizeBy?: 'type' | 'betweenness';
  fitKey?: number;
  onNodeClick?: (n: GNode) => void;
  onBackgroundClick?: () => void;
  legend?: 'types' | 'groups';
  labelAll?: boolean;
}

const idOf = (v: string | GNode) => (typeof v === 'object' ? v.id : v);
const BIG_TYPES = new Set(['Team', 'Api', 'Service', 'Customer', 'Decision', 'Incident']);

function hexA(hex: string, a: number) {
  const n = parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

export default function GraphView({ data, highlight, ripple, colorBy = 'type', sizeBy = 'type', fitKey, onNodeClick, onBackgroundClick, legend = 'types', labelAll = false }: Props) {
  const fg = useRef<any>(null);
  const wrap = useRef<HTMLDivElement>(null);
  const [size, setSize] = useState({ w: 800, h: 600 });
  const [hover, setHover] = useState<GNode | null>(null);

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setSize({ w: el.clientWidth, h: el.clientHeight }));
    ro.observe(el);
    setSize({ w: el.clientWidth, h: el.clientHeight });
    return () => ro.disconnect();
  }, []);

  useEffect(() => {
    const g = fg.current;
    if (!g) return;
    g.d3Force('charge')?.strength(-70).distanceMax(320);
    g.d3Force('link')?.distance((l: GLink) => (l.type === 'COLLABORATES' ? 70 : 38));
  }, [data]);

  // Fit the camera on whatever is highlighted (or everything) whenever fitKey changes.
  useEffect(() => {
    if (fitKey === undefined) return;
    const t = setTimeout(() => {
      const g = fg.current;
      if (!g) return;
      if (highlight.nodes.size > 0) g.zoomToFit(900, 70, (n: GNode) => highlight.nodes.has(n.id));
      else g.zoomToFit(900, 40);
    }, 450);
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fitKey]);

  const hasHl = highlight.nodes.size > 0;
  const maxBetweenness = useMemo(() => Math.max(1, ...data.nodes.map((n) => Number(n.betweenness || 0))), [data]);

  const colorOf = (n: GNode) => {
    if (colorBy === 'group' && typeof n.community === 'number') {
      return n.community < 0 ? '#5F6F6C' : GROUP_COLORS[n.community % GROUP_COLORS.length];
    }
    if (n.type === 'Person' && n.status === 'departed') return '#7D8A87';
    if (n.type === 'Doc' && n.status === 'stale') return '#FF7A59';
    return TYPE_COLOR[n.type] || '#CCCCCC';
  };

  const radiusOf = (n: GNode) => {
    if (sizeBy === 'betweenness') return 4 + 12 * Math.sqrt(Number(n.betweenness || 0) / maxBetweenness);
    return TYPE_RADIUS[n.type] || 4;
  };

  const paintNode = (n: GNode, ctx: CanvasRenderingContext2D, scale: number) => {
    if (n.x === undefined || n.y === undefined) return;
    const r = radiusOf(n);
    const lit = highlight.nodes.has(n.id);
    const dim = hasHl && !lit;
    const color = colorOf(n);
    ctx.save();
    ctx.globalAlpha = dim ? 0.16 : 1;
    if (lit) {
      ctx.shadowColor = color;
      ctx.shadowBlur = 14;
    }
    ctx.beginPath();
    ctx.arc(n.x, n.y, r, 0, 2 * Math.PI);
    if (n.type === 'Person' && n.status === 'departed') {
      ctx.fillStyle = 'rgba(125,138,135,0.25)';
      ctx.fill();
      ctx.setLineDash([2, 1.5]);
      ctx.lineWidth = 1.2;
      ctx.strokeStyle = color;
      ctx.stroke();
      ctx.setLineDash([]);
    } else {
      ctx.fillStyle = color;
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    if (n.type === 'Decision' && n.status === 'superseded') {
      ctx.strokeStyle = 'rgba(255,255,255,0.8)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(n.x - r, n.y + r);
      ctx.lineTo(n.x + r, n.y - r);
      ctx.stroke();
    }
    if (n.type === 'Doc' && n.status === 'stale') {
      const pulse = 1 + 0.35 * Math.sin(Date.now() / 220);
      ctx.strokeStyle = 'rgba(255,122,89,0.9)';
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 2.5 * pulse, 0, 2 * Math.PI);
      ctx.stroke();
    }
    if (n.type === 'Task') {
      ctx.strokeStyle = '#3A2A1A';
      ctx.lineWidth = 1.3;
      ctx.beginPath();
      ctx.moveTo(n.x - r * 0.45, n.y);
      ctx.lineTo(n.x - r * 0.1, n.y + r * 0.4);
      ctx.lineTo(n.x + r * 0.5, n.y - r * 0.4);
      ctx.stroke();
    }
    if (highlight.focus === n.id) {
      ctx.strokeStyle = '#FFFFFF';
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.arc(n.x, n.y, r + 3, 0, 2 * Math.PI);
      ctx.stroke();
    }
    // labels: always for lit nodes; big nodes when zoomed in a bit; everything when zoomed in a lot
    const showLabel = (labelAll && scale > 0.5) || (lit && scale > 0.6) || (!hasHl && BIG_TYPES.has(n.type) && scale > 1.1) || scale > 2.6 || hover?.id === n.id;
    if (showLabel && !dim) {
      const full = nodeLabel(n);
      const label = full.length > 42 ? full.slice(0, 40) + '…' : full;
      const fs = Math.max(10 / scale, 2.2);
      ctx.font = `${lit ? 600 : 500} ${fs}px "Inter Variable", Inter, sans-serif`;
      ctx.textAlign = 'center';
      ctx.textBaseline = 'top';
      const w = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(10,22,20,0.72)';
      ctx.fillRect(n.x - w / 2 - fs * 0.3, n.y + r + fs * 0.3, w + fs * 0.6, fs * 1.25);
      ctx.fillStyle = lit ? '#FFFFFF' : 'rgba(235,245,242,0.85)';
      ctx.fillText(label, n.x, n.y + r + fs * 0.4);
    }
    ctx.restore();
  };

  const paintRipple = (ctx: CanvasRenderingContext2D, scale: number) => {
    if (!ripple) return;
    const o = data.nodes.find((n) => n.id === ripple.origin);
    if (!o || o.x === undefined || o.y === undefined) return;
    const t = (Date.now() - ripple.startedAt) / 1000;
    if (t > 9) return;
    ctx.save();
    for (let k = 0; k < 4; k++) {
      const phase = (t * 0.9 + k * 0.25) % 1;
      const rad = (20 + phase * 360) / Math.max(scale, 0.4);
      const fade = (1 - phase) * Math.max(0, 1 - t / 9);
      ctx.strokeStyle = `rgba(87,193,179,${0.55 * fade})`;
      ctx.lineWidth = (2.5 * (1 - phase) + 0.6) / Math.max(scale, 0.4);
      ctx.beginPath();
      ctx.ellipse(o.x, o.y, rad, rad * 0.92, 0, 0, 2 * Math.PI);
      ctx.stroke();
    }
    ctx.restore();
  };

  const linkColor = (l: GLink) => {
    const lit = highlight.links.has(linkKey(l));
    if (lit) return 'rgba(255,236,190,0.9)';
    if (l.type === 'COLLABORATES') return hasHl ? 'rgba(255,255,255,0.05)' : 'rgba(200,230,225,0.28)';
    return hasHl ? 'rgba(255,255,255,0.035)' : 'rgba(200,230,225,0.13)';
  };

  const types = useMemo(() => {
    const seen = new Set(data.nodes.map((n) => n.type));
    return Object.keys(TYPE_COLOR).filter((t) => seen.has(t as GNode['type']));
  }, [data]);

  return (
    <div className="graph-wrap" ref={wrap}>
      <ForceGraph2D
        ref={fg}
        width={size.w}
        height={size.h}
        graphData={data}
        backgroundColor="rgba(0,0,0,0)"
        nodeId="id"
        nodeCanvasObject={(n: any, ctx: CanvasRenderingContext2D, s: number) => paintNode(n as GNode, ctx, s)}
        nodePointerAreaPaint={(n: any, color: string, ctx: CanvasRenderingContext2D) => {
          ctx.fillStyle = color;
          ctx.beginPath();
          ctx.arc(n.x, n.y, radiusOf(n) + 2, 0, 2 * Math.PI);
          ctx.fill();
        }}
        linkColor={(l: any) => linkColor(l)}
        linkWidth={(l: any) => (highlight.links.has(linkKey(l)) ? 2 : l.type === 'COLLABORATES' ? 0.4 + 0.25 * Number(l.weight || 1) : 0.6)}
        linkDirectionalParticles={(l: any) => (highlight.links.has(linkKey(l)) ? 3 : 0)}
        linkDirectionalParticleWidth={2.6}
        linkDirectionalParticleSpeed={0.008}
        linkDirectionalParticleColor={() => '#FFD877'}
        onRenderFramePost={(ctx: CanvasRenderingContext2D, s: number) => paintRipple(ctx, s)}
        onNodeClick={(n: any) => onNodeClick?.(n)}
        onNodeHover={(n: any) => setHover(n || null)}
        onBackgroundClick={() => onBackgroundClick?.()}
        autoPauseRedraw={false}
        cooldownTicks={160}
        d3AlphaDecay={0.025}
        d3VelocityDecay={0.32}
        minZoom={0.3}
        maxZoom={8}
      />
      {hover && (
        <div className="graph-hover">
          <span className="dot" style={{ background: colorOf(hover) }} />
          <b>{TYPE_LABEL[hover.type] || hover.type}</b> · {nodeLabel(hover)}
          {hover.status === 'departed' && <em> · left {String(hover.left || '')}</em>}
          {hover.status === 'stale' && <em> · stale</em>}
        </div>
      )}
      {legend === 'types' && (
        <div className="legend">
          {types.map((t) => (
            <span key={t}><i style={{ background: TYPE_COLOR[t] }} />{TYPE_LABEL[t] || t}</span>
          ))}
          <span><i className="ring-departed" />Has left</span>
          <span><i style={{ background: '#FF7A59' }} />Stale doc</span>
        </div>
      )}
    </div>
  );
}
