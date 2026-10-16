import type { NodeType } from './types';

export const TYPE_COLOR: Record<string, string> = {
  Person: '#F6C453',
  Team: '#E9D8B4',
  Service: '#5CC8B8',
  Api: '#8FD3F4',
  Customer: '#F49A7A',
  Decision: '#C3A6F2',
  Doc: '#A8D672',
  Incident: '#FF6B6B',
  Meeting: '#F2A7CF',
  Message: '#9DB5B0',
  Ticket: '#D9B98C',
  PR: '#B7C3F2',
  Task: '#FFD166',
  Claim: '#A8D672',
  Alternative: '#9A9A9A',
  Channel: '#9DB5B0',
  Answer: '#FFFFFF',
  Entity: '#CCCCCC',
};

export const TYPE_RADIUS: Record<string, number> = {
  Team: 9, Api: 9, Service: 7, Customer: 7, Decision: 7.5, Incident: 7, Person: 5.5, Doc: 5.5,
  Meeting: 5, Task: 5.5, Message: 3.6, Ticket: 4, PR: 4, Claim: 3, Alternative: 4, Channel: 4, Answer: 4, Entity: 4,
};

export const TYPE_LABEL: Record<string, string> = {
  Person: 'Person', Team: 'Team', Service: 'Service', Api: 'API', Customer: 'Customer', Decision: 'Decision',
  Doc: 'Doc', Incident: 'Incident', Meeting: 'Meeting', Message: 'Message', Ticket: 'Ticket', PR: 'Pull request',
  Task: 'Task', Claim: 'Doc statement', Alternative: 'Rejected option', Channel: 'Channel', Answer: 'Answer',
};

export const TYPE_ICON: Record<string, string> = {
  Person: '👤', Team: '👥', Service: '⚙️', Api: '🔌', Customer: '🏢', Decision: '⚖️', Doc: '📄', Incident: '🔥',
  Meeting: '🗓️', Message: '💬', Ticket: '🎫', PR: '🔀', Task: '✅', Claim: '📝', Alternative: '✖️', Channel: '#',
};

// Colors for collaboration groups in the X-ray view.
export const GROUP_COLORS = ['#F6C453', '#5CC8B8', '#F49A7A', '#C3A6F2', '#8FD3F4', '#A8D672', '#F2A7CF', '#D9B98C'];

export const TOOL_LABEL: Record<string, string> = {
  trace_decision: 'Tracing the decision',
  who_knows: 'Finding who knows',
  impact_of: 'Following the impact',
  open_work: 'Checking open work',
  search: 'Searching everything',
  get_details: 'Reading details',
  graph_query: 'Running a Cypher query',
};

export function nodeLabel(n: { name?: string; title?: string; id: string }): string {
  return (n.name || n.title || n.id) as string;
}

export function typeOf(t: string): NodeType {
  return (t in TYPE_COLOR ? t : 'Entity') as NodeType;
}
