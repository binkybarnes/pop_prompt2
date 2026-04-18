import type { LaneFile } from '@/lib/types';
import { fmtInt, fmtWeeks } from '@/lib/format';

export function BacktestTab({ lane }: { lane: LaneFile }) {
  const alertRows = lane.series.filter((r) => r.alert_fired_mean || r.alert_fired_p90);
  const tpCount = alertRows.filter(
    (r) => r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;
  const stockoutCount = lane.series.filter((r) => r.fresh_stockout).length;
  const totalAlerts = alertRows.length;

  const precision = totalAlerts > 0 ? (tpCount / totalAlerts) * 100 : 0;
  const recall = stockoutCount > 0 ? (tpCount / stockoutCount) * 100 : 0;
  const warningWeeks = alertRows
    .map((r) => r.weeks_until_stockout)
    .filter((w): w is number => w !== null)
    .sort((a, b) => a - b);
  const median = warningWeeks.length > 0
    ? warningWeeks[Math.floor(warningWeeks.length / 2)]
    : null;

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm">
        <div className="flex flex-wrap gap-6">
          <Stat label="Precision" value={`${precision.toFixed(0)}%`} />
          <Stat label="Recall" value={`${recall.toFixed(0)}%`} />
          <Stat label="Median warning" value={median !== null ? fmtWeeks(median) : '—'} />
          <Stat label="Alerts fired" value={fmtInt(totalAlerts)} />
          <Stat label="Real stockouts" value={fmtInt(stockoutCount)} />
        </div>
      </div>
      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-3 py-2">Week</th>
              <th className="px-3 py-2 text-right">Reorder pt (mean)</th>
              <th className="px-3 py-2 text-right">Reorder pt (p90)</th>
              <th className="px-3 py-2 text-right">On hand</th>
              <th className="px-3 py-2 text-center">Mean alert</th>
              <th className="px-3 py-2 text-center">P90 alert</th>
              <th className="px-3 py-2 text-right">Wks to stockout</th>
            </tr>
          </thead>
          <tbody>
            {alertRows.slice(-40).reverse().map((r) => (
              <tr key={r.week_start} className="border-t border-border hover:bg-gray-50">
                <td className="px-3 py-1.5 font-mono text-[13px]">{r.week_start}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.reorder_point_mean)}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.reorder_point_p90)}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.on_hand_est)}</td>
                <td className="px-3 py-1.5 text-center">{r.alert_fired_mean ? '●' : ''}</td>
                <td className="px-3 py-1.5 text-center">{r.alert_fired_p90 ? '●' : ''}</td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  {r.weeks_until_stockout !== null ? fmtWeeks(r.weeks_until_stockout) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <div className="text-xs uppercase tracking-wider text-muted">{label}</div>
      <div className="font-mono text-lg font-semibold text-fg">{value}</div>
    </div>
  );
}
