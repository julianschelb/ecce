export function formatNumber(value: number): string {
  return new Intl.NumberFormat("en", { maximumFractionDigits: 0 }).format(value);
}

export function formatWeight(value: number): string {
  return value >= 100 ? value.toFixed(0) : value >= 10 ? value.toFixed(1) : value.toFixed(2);
}

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "" : date.toLocaleDateString("en", { year: "numeric", month: "short", day: "numeric" });
}

/** Split a backend snippet with <mark> tags into plain/highlighted segments (no HTML injection). */
export function splitSnippet(snippet: string): Array<{ text: string; mark: boolean }> {
  const parts: Array<{ text: string; mark: boolean }> = [];
  const re = /<mark>(.*?)<\/mark>/gs;
  let last = 0;
  for (const match of snippet.matchAll(re)) {
    const index = match.index ?? 0;
    if (index > last) parts.push({ text: snippet.slice(last, index), mark: false });
    parts.push({ text: match[1], mark: true });
    last = index + match[0].length;
  }
  if (last < snippet.length) parts.push({ text: snippet.slice(last), mark: false });
  return parts;
}
