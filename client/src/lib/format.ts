/** Presentation helpers shared across features. */

export function formatPercent(score: number): string {
  const value = score <= 1 ? score * 100 : score;
  return `${Math.max(0, Math.min(100, value)).toFixed(0)}%`;
}

export function formatDate(iso?: string): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toLocaleString();
}

export function truncate(text: string, max = 90): string {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

const TYPE_COLORS = [
  "var(--accent-1)",
  "var(--accent-2)",
  "var(--accent-3)",
  "var(--accent-4)",
  "var(--accent-5)",
];

/** Stable colour per cluster type / cluster id. */
export function colorForKey(key: string | number): string {
  const str = String(key);
  let hash = 0;
  for (let i = 0; i < str.length; i += 1) hash = (hash * 31 + str.charCodeAt(i)) >>> 0;
  return TYPE_COLORS[hash % TYPE_COLORS.length];
}
