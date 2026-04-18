import type { LaneFile, LaneIndexRow } from '@/lib/types';
import { fmtCases, fmtFloat, fmtInt, fmtPct, fmtWeeks } from '@/lib/format';

export function SidePanel({
  lane,
  laneSummary,
}: {
  lane: LaneFile;
  laneSummary: LaneIndexRow | undefined;
}) {
  const t = lane.today;
  const m = lane.metadata;

  return (
    <aside className="w-[280px] shrink-0 space-y-4">
      {t.reorder_flag && (
        <Card title="Why firing?">
          <Row label="Available" value={fmtInt(t.available)} />
          <Row label="Reorder point" value={fmtInt(t.reorder_point)} />
          <Row
            label="Gap"
            value={
              t.available !== null && t.reorder_point !== null
                ? fmtInt(t.reorder_point - t.available)
                : '—'
            }
          />
          <Row label="Suggest" value={`${fmtInt(t.suggested_qty)} u · ${fmtCases(t.suggested_cases)}`} />
          <p className="mt-2 text-xs leading-snug text-muted">
            {t.lead_time_wk !== null && t.run_rate_wk !== null
              ? `${fmtWeeks(t.lead_time_wk)} × ${fmtInt(t.run_rate_wk)}/wk = ${fmtInt(t.lead_time_wk * t.run_rate_wk)} needed, + ${fmtInt(t.safety_stock)} safety = ${fmtInt(t.reorder_point)} reorder point.`
              : 'Insufficient data for derivation.'}
          </p>
        </Card>
      )}

      <Card title="SKU metadata">
        <Row label="Brand" value={laneSummary?.brand || '—'} />
        <Row label="Case pack" value={m.case_pack !== null ? String(m.case_pack) : '—'} />
        <Row label="Vendor" value={m.vendor || '—'} />
        <Row label="Country" value={m.country || '—'} />
        <Row
          label="Lead time"
          value={`${fmtWeeks(t.lead_time_wk)}${t.lead_time_source ? ` (${t.lead_time_source})` : ''}`}
        />
      </Card>

      <Card title="Lane stats">
        <Row label="Fresh rate" value={laneSummary ? fmtPct(laneSummary.fresh_rate * 100, 1) : '—'} />
        <Row label="Run rate" value={`${fmtInt(t.run_rate_wk)}/wk`} />
        <Row label="CV (weekly)" value={
          t.std_wk !== null && t.run_rate_wk !== null && t.run_rate_wk > 0
            ? fmtFloat(t.std_wk / t.run_rate_wk, 2)
            : '—'
        } />
        <Row label="Clean weeks" value={fmtInt(t.n_clean_weeks)} />
      </Card>
    </aside>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <h3 className="mb-2 text-xs uppercase tracking-wider text-muted">{title}</h3>
      <div className="space-y-1 text-sm">{children}</div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-2">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-[13px] text-fg">{value}</span>
    </div>
  );
}
