export type NodeType =
  | 'Person' | 'Team' | 'Service' | 'Api' | 'Customer' | 'Decision' | 'Doc' | 'Incident' | 'Meeting'
  | 'Message' | 'Ticket' | 'PR' | 'Task' | 'Claim' | 'Alternative' | 'Channel' | 'Answer' | 'Entity';

export interface GNode {
  id: string;
  type: NodeType;
  name?: string;
  title?: string;
  status?: string;
  at?: string;
  ts?: string;
  left?: string;
  kind?: string;
  channel?: string;
  team?: string;
  community?: number;
  betweenness?: number;
  summary?: string;
  [k: string]: unknown;
  // force-graph runtime fields
  x?: number;
  y?: number;
  vx?: number;
  vy?: number;
}

export interface GLink {
  source: string | GNode;
  target: string | GNode;
  type: string;
  weight?: number;
}

export interface CypherRun { name: string; cypher: string; params: Record<string, unknown> }

export interface Source { key: string; id: string; type: NodeType; title: string; at: string; snippet: string }

export interface TraceStep {
  id: string;
  name: string;
  args: Record<string, unknown>;
  summary?: string;
  cypher?: CypherRun[];
  done: boolean;
}

export interface MemoryHit {
  question: string; answer: string; at?: string; sources: number;
  stale_sources: { id: string; name: string; status: string }[];
}

export interface ChatTurn {
  id: string;
  question: string;
  status?: string;
  reasoning: string;
  steps: TraceStep[];
  answer: string;
  sources: Source[];
  cited: string[];
  memory?: MemoryHit;
  seconds?: number;
  error?: string;
  done: boolean;
}

export interface Proposal {
  pid: string; kind: string; title: string; priority: string;
  assignee: GNode | null; because: string; targets: string[]; draft: string | null;
}

export interface StaleDoc {
  doc: GNode;
  claims: { id: string; text: string; verdict: string; why: string; rewrite: string }[];
}

export interface ConflictItem { id: string; decision: string; relation: string; reason: string; by: string[] }

export interface PresetEvent { id: string; label: string; channel: string; author: string; author_name: string; text: string; ts: string }
