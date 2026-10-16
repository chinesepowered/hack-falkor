import { Fragment, type ReactNode } from 'react';

const INLINE = /(\*\*[^*]+\*\*|`[^`]+`|\[S\d+(?:\s*[,;]\s*S\d+)*\])/g;

function inline(text: string, onCite?: (key: string) => void, cited?: Set<string>): ReactNode[] {
  return text.split(INLINE).filter(Boolean).map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) return <strong key={i}>{part.slice(2, -2)}</strong>;
    if (part.startsWith('`') && part.endsWith('`')) return <code key={i}>{part.slice(1, -1)}</code>;
    const m = part.match(/^\[(S\d+(?:\s*[,;]\s*S\d+)*)\]$/);
    if (m) {
      return (
        <Fragment key={i}>
          {m[1].split(/\s*[,;]\s*/).map((k) => (
            <button key={k} className={`cite ${cited?.has(k) ? 'on' : ''}`} onClick={() => onCite?.(k)} title={`Source ${k}`}>
              {k.slice(1)}
            </button>
          ))}
        </Fragment>
      );
    }
    return <Fragment key={i}>{part}</Fragment>;
  });
}

/** Tiny Markdown renderer: paragraphs, bullet lists, bold, inline code and [S#] citation chips. */
export default function Markdown({ text, onCite, cited }: { text: string; onCite?: (key: string) => void; cited?: Set<string> }) {
  const out: ReactNode[] = [];
  let list: string[] = [];
  const flush = () => {
    if (list.length) {
      out.push(<ul key={`ul${out.length}`}>{list.map((li, i) => <li key={i}>{inline(li, onCite, cited)}</li>)}</ul>);
      list = [];
    }
  };
  for (const raw of text.split('\n')) {
    const line = raw.trimEnd();
    const bullet = line.match(/^\s*(?:[-*•]|\d+\.)\s+(.*)$/);
    if (bullet) {
      list.push(bullet[1]);
      continue;
    }
    flush();
    if (!line.trim()) continue;
    const heading = line.match(/^#+\s+(.*)$/);
    if (heading) out.push(<p key={`h${out.length}`} className="md-h">{inline(heading[1], onCite, cited)}</p>);
    else out.push(<p key={`p${out.length}`}>{inline(line, onCite, cited)}</p>);
  }
  flush();
  return <div className="md">{out}</div>;
}
