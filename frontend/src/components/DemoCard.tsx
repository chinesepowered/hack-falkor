import Capy from './Capy';

const FEATURES = [
  ['Vector index', 'where to start'],
  ['Full-text index', 'names, fuzzy'],
  ['Multi-hop Cypher', 'the trail behind every answer'],
  ['labelPropagation · betweenness · pageRank', 'the shape of the org'],
  ['GRAPH.COPY', 'seed, reset, ablation'],
  ['GRAPH.RO_QUERY', "the agent's own Cypher, read-only"],
];

/** Title cards for the demo video: /?card=intro and /?card=outro */
export default function DemoCard({ kind }: { kind: string }) {
  if (kind === 'outro') {
    return (
      <div className="card-stage">
        <div className="card-outro">
          <div className="outro-left">
            <Capy mood="happy" size={360} bath />
          </div>
          <div className="outro-right">
            <div className="kicker">How CapyBrain runs on FalkorDB</div>
            <div className="feature-grid">
              {FEATURES.map(([a, b], i) => (
                <div key={a} className="feature" style={{ animationDelay: `${0.25 + i * 0.18}s` }}>
                  <b>{a}</b><span>{b}</span>
                </div>
              ))}
            </div>
            <h1 className="title small">CapyBrain</h1>
            <p className="tagline">Knows everyone. Remembers why. Stays calm when things change.</p>
            <p className="foot">github.com/chinesepowered/hack-falkor · Graph Hacks 2026 · Company Brain track</p>
          </div>
        </div>
      </div>
    );
  }
  return (
    <div className="card-stage">
      <div className="card-intro">
        <div className="intro-capy"><Capy mood="idle" size={460} bath /></div>
        <h1 className="title">CapyBrain</h1>
        <p className="tagline">Knows everyone. Remembers why. Stays calm when things change.</p>
        <p className="foot">A company brain on FalkorDB · Graph Hacks 2026 · Company Brain track</p>
      </div>
    </div>
  );
}
