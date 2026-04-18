import type { LaneFile } from '@/lib/types';
import { fmtCases, fmtInt, fmtWeeks } from '@/lib/format';

export function LaneHeader({ lane }: { lane: LaneFile }) {
  const t = lane.today;
  const conf = t.confidence;
  const confColor =
    conf === 'high' ? 'bg-ok/10 text-ok' :
    conf === 'medium' ? 'bg-warn/10 text-warn' :
    'bg-gray-200 text-muted';

  const recommendation = t.reorder_flag
    ? `Alert firing · suggest ${fmtCases(t.suggested_cases)} · lead time ${fmtWeeks(t.lead_time_wk)} · run rate ${fmtInt(t.run_rate_wk)}/wk`
    : `No alert · ${fmtWeeks(t.weeks_of_cover)} cover · run rate ${fmtInt(t.run_rate_wk)}/wk`;

  return (
    <div className="rounded-md border border-border bg-surface px-5 py-3">
      <div className="flex items-center gap-3">
        <h1 className="font-mono text-lg font-semibold text-fg">{lane.sku}</h1>
        <span className="text-sm text-muted">·</span>
        <span className="text-sm text-fg">{lane.metadata.sku_desc}</span>
        <span className="text-sm text-muted">·</span>
        <span className="font-mono text-sm text-fg">{lane.dc}</span>
        <span className={`ml-auto rounded-full px-2 py-0.5 text-[11px] font-medium ${confColor}`}>
          {conf}
        </span>
      </div>
      <p className={`mt-2 text-sm ${t.reorder_flag ? 'text-alert' : 'text-muted'}`}>
        {recommendation}
      </p>
    </div>
  );
}
