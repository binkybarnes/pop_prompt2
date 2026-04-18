import type { AlertRow, BacktestSummary } from '@/lib/types';

export function SummaryStats({
  rows,
  dc,
  confidence,
  status,
}: {
  rows: AlertRow[];
  dc: string;
  confidence: string;
  status: string;
  summary: BacktestSummary;
}) {
  const filtered = rows.filter((r) => {
    if (dc !== 'all' && r.DC !== dc) return false;
    if (confidence !== 'all' && r.confidence !== confidence) return false;
    if (status === 'flagged' && !r.reorder_flag) return false;
    if (status === 'not_flagged' && r.reorder_flag) return false;
    return true;
  });
  const flagged = filtered.filter((r) => r.reorder_flag).length;
  const high = filtered.filter((r) => r.reorder_flag && r.confidence === 'high').length;
  const med = filtered.filter((r) => r.reorder_flag && r.confidence === 'medium').length;
  const low = filtered.filter((r) => r.reorder_flag && r.confidence === 'low').length;

  return (
    <div className="flex items-baseline gap-6 rounded-md border border-border bg-surface px-4 py-2 text-sm">
      <span>
        <span className="font-semibold text-fg">{flagged}</span>
        <span className="ml-1 text-muted">alerts firing</span>
      </span>
      <span className="text-muted">·</span>
      <span>
        <span className="font-semibold text-ok">{high}</span>
        <span className="ml-1 text-muted">high</span>
      </span>
      <span>
        <span className="font-semibold text-warn">{med}</span>
        <span className="ml-1 text-muted">medium</span>
      </span>
      <span>
        <span className="font-semibold text-muted">{low}</span>
        <span className="ml-1 text-muted">low</span>
      </span>
      <span className="ml-auto text-xs text-muted">{filtered.length} rows shown</span>
    </div>
  );
}
