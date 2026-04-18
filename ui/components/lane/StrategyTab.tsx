import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function StrategyTab({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const meanAlerts = lane.series.filter((r) => r.alert_fired_mean).length;
  const p90Alerts = lane.series.filter((r) => r.alert_fired_p90).length;
  const stockouts = lane.series.filter((r) => r.fresh_stockout).length;
  const meanTP = lane.series.filter(
    (r) => r.alert_fired_mean && r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;
  const p90TP = lane.series.filter(
    (r) => r.alert_fired_p90 && r.weeks_until_stockout !== null && r.weeks_until_stockout <= 12
  ).length;

  const meanOrders = counterfactual.simulated_pos
    .filter((p) => p.strategy === 'mean')
    .reduce((acc, p) => acc + p.qty, 0);
  const p90Orders = counterfactual.simulated_pos
    .filter((p) => p.strategy === 'p90')
    .reduce((acc, p) => acc + p.qty, 0);

  return (
    <div className="grid grid-cols-2 gap-4">
      <StratCard
        title="Mean"
        alerts={meanAlerts}
        tp={meanTP}
        stockouts={stockouts}
        totalOrdered={meanOrders}
        accent="text-ok"
      />
      <StratCard
        title="P90"
        alerts={p90Alerts}
        tp={p90TP}
        stockouts={stockouts}
        totalOrdered={p90Orders}
        accent="text-cyan-700"
      />
      <p className="col-span-2 text-xs italic text-muted">
        Mean uses the average weekly clean-demand run rate. P90 uses the 90th-percentile
        weekly run rate, widening the safety buffer — fires more alerts but catches more
        real stockouts.
      </p>
    </div>
  );
}

function StratCard({
  title,
  alerts,
  tp,
  stockouts,
  totalOrdered,
  accent,
}: {
  title: string;
  alerts: number;
  tp: number;
  stockouts: number;
  totalOrdered: number;
  accent: string;
}) {
  const fp = alerts - tp;
  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3">
      <h3 className={`text-sm font-semibold ${accent}`}>{title}</h3>
      <dl className="mt-2 space-y-1 text-sm">
        <StatRow label="Alerts fired" value={fmtInt(alerts)} />
        <StatRow label="True positives" value={fmtInt(tp)} />
        <StatRow label="False positives" value={fmtInt(fp)} />
        <StatRow label="Real stockouts" value={fmtInt(stockouts)} />
        <StatRow label="Simulated units ordered" value={fmtInt(totalOrdered)} />
      </dl>
    </div>
  );
}

function StatRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-muted">{label}</span>
      <span className="font-mono text-[13px] text-fg">{value}</span>
    </div>
  );
}
