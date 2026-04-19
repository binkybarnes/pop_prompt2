import type { LaneFile } from '@/lib/types';
import { fmtInt, fmtWeeks } from '@/lib/format';

export function BacktestTab({ lane }: { lane: LaneFile }) {
  const alertRows = lane.series.filter((r) => r.alert_fired);
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

  const eventRows = lane.series
    .filter((r) => r.alert_fired || r.po_ordered || r.po_received || r.fresh_stockout)
    .slice(-50)
    .reverse();

  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm">
        <div className="flex flex-wrap gap-6">
          <Stat label="Precision" value={`${precision.toFixed(0)}%`} />
          <Stat label="Recall" value={`${recall.toFixed(0)}%`} />
          <Stat label="Median warning" value={median !== null ? fmtWeeks(median) : '—'} />
          <Stat label="Alerts fired" value={fmtInt(totalAlerts)} />
          <Stat label="Real stockouts" value={fmtInt(stockoutCount)} />
          <Stat label="POs placed" value={fmtInt(lane.simulated_pos.length)} />
        </div>
      </div>
      <div className="overflow-hidden rounded-md border border-border bg-surface">
        <table className="w-full text-sm">
          <thead className="bg-gray-50 text-left text-xs uppercase tracking-wider text-muted">
            <tr>
              <th className="px-3 py-2">Week</th>
              <th className="px-3 py-2 text-right">On hand (sim)</th>
              <th className="px-3 py-2 text-right">Reorder pt</th>
              <th className="px-3 py-2">Regime</th>
              <th className="px-3 py-2 text-center">Events</th>
              <th className="px-3 py-2 text-right">Wks to stockout</th>
            </tr>
          </thead>
          <tbody>
            {eventRows.map((r) => {
              const events: string[] = [];
              if (r.alert_fired) events.push('alert');
              if (r.po_ordered) events.push('PO');
              if (r.po_received) events.push('recv');
              if (r.fresh_stockout) events.push('stockout');
              return (
                <tr key={r.week_start} className="border-t border-border hover:bg-gray-50">
                  <td className="px-3 py-1.5 font-mono text-[13px]">{r.week_start}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.on_hand_sim)}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-[13px]">{fmtInt(r.reorder_point)}</td>
                  <td className="px-3 py-1.5 text-[12px] text-muted">{r.regime ?? '—'}</td>
                  <td className="px-3 py-1.5 text-center text-[12px]">{events.join(' · ')}</td>
                  <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                    {r.weeks_until_stockout !== null ? fmtWeeks(r.weeks_until_stockout) : '—'}
                  </td>
                </tr>
              );
            })}
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
