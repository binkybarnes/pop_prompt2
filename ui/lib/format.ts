export function fmtInt(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return Math.round(n).toLocaleString('en-US');
}

export function fmtFloat(n: number | null | undefined, digits = 1): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits });
}

export function fmtPct(n: number | null | undefined, digits = 0): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${n.toLocaleString('en-US', { maximumFractionDigits: digits, minimumFractionDigits: digits })}%`;
}

export function fmtWeeks(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${n.toLocaleString('en-US', { maximumFractionDigits: 0 })} wk`;
}

export function fmtCases(n: number | null | undefined): string {
  if (n === null || n === undefined || Number.isNaN(n)) return '—';
  return `${Math.round(n).toLocaleString('en-US')} cs`;
}

export function slugOf(sku: string, dc: string): string {
  return `${sku}-${dc}`;
}

export function parseSlug(slug: string): { sku: string; dc: string } {
  const idx = slug.lastIndexOf('-');
  return { sku: slug.slice(0, idx), dc: slug.slice(idx + 1) };
}
