import type { ReactNode } from "react";

const LINKED: Array<[RegExp, (match: RegExpExecArray) => string]> = [
  [/Project Gutenberg #(\d+)/, (m) => `https://www.gutenberg.org/ebooks/${m[1]}`],
  [/Perseus Digital Library(?:, canonical-latinLit)?/, () => "https://github.com/PerseusDL/canonical-latinLit"],
  [/CC BY-SA 4\.0/, () => "https://creativecommons.org/licenses/by-sa/4.0/"],
];

/** A corpus's source line with links to the source (Project Gutenberg asks for a link to the
 * book's page) and to the licence, where one applies (CC BY-SA requires naming it). */
export function SourceCredit({ source }: { source: string }) {
  const parts: ReactNode[] = [];
  let rest = source;
  while (rest) {
    const hits = LINKED.map(([re, href]) => {
      const m = re.exec(rest);
      return m ? { m, href: href(m) } : null;
    }).filter((h): h is { m: RegExpExecArray; href: string } => h !== null);
    if (!hits.length) {
      parts.push(rest);
      break;
    }
    const first = hits.reduce((a, b) => (b.m.index < a.m.index ? b : a));
    if (first.m.index > 0) parts.push(rest.slice(0, first.m.index));
    parts.push(
      <a key={parts.length} className="underline decoration-line hover:text-ink" href={first.href} target="_blank" rel="noreferrer">
        {first.m[0]}
      </a>,
    );
    rest = rest.slice(first.m.index + first.m[0].length);
  }
  return <>{parts}</>;
}
