import type { GLink, GNode, PresetEvent, Proposal } from './types';

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  return res.json() as Promise<T>;
}

export const api = {
  health: () => fetch('/api/health').then((r) => json<any>(r)),
  graph: () => fetch('/api/graph').then((r) => json<{ nodes: GNode[]; links: GLink[] }>(r)),
  node: (id: string) => fetch(`/api/node/${encodeURIComponent(id)}`).then((r) => json<any>(r)),
  xray: () => fetch('/api/xray').then((r) => json<any>(r)),
  events: () => fetch('/api/events').then((r) => json<PresetEvent[]>(r)),
  baseline: (question: string) =>
    fetch('/api/baseline', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ question }) })
      .then((r) => json<{ answer: string; seconds: number; snippets: { n: number; id: string; type: string; title: string; at: string }[] }>(r)),
  approve: (decision_id: string, items: Proposal[]) =>
    fetch('/api/tasks/approve', { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ decision_id, items }) })
      .then((r) => json<{ nodes: GNode[]; links: GLink[]; created: number }>(r)),
  reset: () => fetch('/api/reset', { method: 'POST' }).then((r) => json<any>(r)),
};

/** POST a JSON body and read the server-sent event stream, one parsed object per event. */
export async function stream(path: string, body: unknown, onEvent: (ev: any) => void, signal?: AbortSignal): Promise<void> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify(body),
    signal,
  });
  if (!res.ok || !res.body) throw new Error(`${res.status} ${res.statusText}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    let idx: number;
    while ((idx = buf.indexOf('\n\n')) >= 0) {
      const chunk = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      for (const line of chunk.split('\n')) {
        if (line.startsWith('data: ')) {
          try {
            onEvent(JSON.parse(line.slice(6)));
          } catch {
            /* ignore malformed line */
          }
        }
      }
    }
  }
}
