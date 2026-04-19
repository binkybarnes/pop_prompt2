'use client';

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceDot,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { useMemo } from 'react';
import type { LaneFile } from '@/lib/types';
import { fmtInt, fmtWeeks } from '@/lib/format';

const HISTORY_WEEKS = 13;
const MIN_FORWARD_WEEKS = 8;

type Row = {
  week_start: string;
  on_hand_actual: number | null;
  burn_no_order: number | null;
  burn_if_ordered: number | null;
};

function addWeeks(iso: string, weeks: number): string {
  const d = new Date(iso + 'T00:00:00Z');
  d.setUTCDate(d.getUTCDate() + weeks * 7);
  return d.toISOString().slice(0, 10);
}

export function OperationalChart({ lane }: { lane: LaneFile }) {
  const { today, series } = lane;
  const lastRow = series.length ? series[series.length - 1] : null;
  const asOfWeek = lastRow?.week_start ?? null;

  const { data, poArrivalWeek, poArrivalOnHand, weeksToZero } = useMemo(() => {
    if (!asOfWeek || lastRow?.on_hand_est == null) {
      return { data: [] as Row[], poArrivalWeek: null, poArrivalOnHand: null, weeksToZero: null };
    }

    const startOnHand = lastRow.on_hand_est;
    const runRate = today.run_rate_wk && today.run_rate_wk > 0 ? today.run_rate_wk : 0;
    const leadWeeks = today.lead_time_wk ?? 0;
    const suggested = today.suggested_qty ?? 0;
    const wksToZero = runRate > 0 ? Math.ceil(startOnHand / runRate) : null;

    const horizon = Math.max(
      MIN_FORWARD_WEEKS,
      Math.ceil(leadWeeks) + 4,
      (wksToZero ?? 0) + 2,
    );

    // History: N weeks ending one week before asOfWeek (asOfWeek is the transition point)
    const lastIdx = series.length - 1;
    const historyStart = Math.max(0, lastIdx - HISTORY_WEEKS + 1);
    const history: Row[] = series.slice(historyStart, lastIdx).map((r) => ({
      week_start: r.week_start,
      on_hand_actual: r.on_hand_est,
      burn_no_order: null,
      burn_if_ordered: null,
    }));

    // Transition: actual + projection share this point so the lines meet visually
    const transition: Row = {
      week_start: asOfWeek,
      on_hand_actual: startOnHand,
      burn_no_order: startOnHand,
      burn_if_ordered: today.reorder_flag ? startOnHand : null,
    };

    // Future projection
    const future: Row[] = [];
    for (let w = 1; w <= horizon; w++) {
      const ws = addWeeks(asOfWeek, w);
      const burnNo = runRate > 0 ? Math.max(0, startOnHand - runRate * w) : null;
      let burnIf: number | null = null;
      if (today.reorder_flag && runRate > 0 && leadWeeks > 0) {
        if (w < leadWeeks) {
          burnIf = Math.max(0, startOnHand - runRate * w);
        } else {
          const onHandAtArrival = Math.max(0, startOnHand - runRate * leadWeeks);
          burnIf = Math.max(0, onHandAtArrival + suggested - runRate * (w - leadWeeks));
        }
      }
      future.push({
        week_start: ws,
        on_hand_actual: null,
        burn_no_order: burnNo,
        burn_if_ordered: burnIf,
      });
    }

    const arrivalWeek =
      today.reorder_flag && leadWeeks > 0 ? addWeeks(asOfWeek, Math.ceil(leadWeeks)) : null;
    const arrivalOnHand =
      today.reorder_flag && runRate > 0 && leadWeeks > 0
        ? Math.max(0, startOnHand - runRate * leadWeeks) + suggested
        : null;

    return {
      data: [...history, transition, ...future],
      poArrivalWeek: arrivalWeek,
      poArrivalOnHand: arrivalOnHand,
      weeksToZero: wksToZero,
    };
  }, [today, series, asOfWeek, lastRow]);

  if (data.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-4 text-sm text-muted">
        Not enough data to project — missing current on-hand or inventory snapshot week.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <div className="mb-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <h3 className="text-sm font-semibold text-fg">Prediction — forward projection</h3>
        <span className="text-xs text-muted">
          as of {asOfWeek} · on-hand {fmtInt(lastRow?.on_hand_est ?? null)} · run rate {fmtInt(today.run_rate_wk)}/wk
        </span>
      </div>

      <ResponsiveContainer width="100%" height={320}>
        <ComposedChart data={data} margin={{ top: 16, right: 24, left: 12, bottom: 12 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
          <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={40} />
          <YAxis
            tick={{ fontSize: 11, fill: '#6b7280' }}
            tickFormatter={(v) => fmtInt(v as number)}
            width={72}
          />
          <Tooltip
            contentStyle={{ fontSize: 12 }}
            formatter={(v, name) => {
              if (v === null || v === undefined) return ['—', name as string];
              const num = typeof v === 'number' ? v : Number(v);
              if (Number.isNaN(num)) return ['—', name as string];
              return [fmtInt(num), name as string];
            }}
          />
          <Legend wrapperStyle={{ fontSize: 12 }} />

          {today.reorder_point != null && (
            <ReferenceLine
              y={today.reorder_point}
              stroke="#f59e0b"
              strokeDasharray="5 4"
              strokeWidth={1.2}
              label={{
                value: `ROP ${fmtInt(today.reorder_point)}`,
                position: 'insideTopRight',
                fontSize: 11,
                fill: '#f59e0b',
              }}
            />
          )}
          {today.safety_stock != null && (
            <ReferenceLine
              y={today.safety_stock}
              stroke="#dc2626"
              strokeDasharray="2 3"
              strokeWidth={1.2}
              label={{
                value: `SS ${fmtInt(today.safety_stock)}`,
                position: 'insideBottomRight',
                fontSize: 11,
                fill: '#dc2626',
              }}
            />
          )}
          {asOfWeek && (
            <ReferenceLine
              x={asOfWeek}
              stroke="#6b7280"
              strokeDasharray="3 3"
              strokeWidth={1}
              label={{ value: 'today', position: 'top', fontSize: 11, fill: '#6b7280' }}
            />
          )}

          <Line
            type="monotone"
            dataKey="on_hand_actual"
            name="on_hand (actual)"
            stroke="#1b2a4a"
            strokeWidth={2}
            dot={false}
            connectNulls={false}
          />
          <Line
            type="monotone"
            dataKey="burn_no_order"
            name="if you don't order"
            stroke="#dc2626"
            strokeDasharray="4 3"
            strokeWidth={1.5}
            dot={false}
            connectNulls={false}
          />
          {today.reorder_flag && (
            <Line
              type="monotone"
              dataKey="burn_if_ordered"
              name="if you order today"
              stroke="#16a34a"
              strokeDasharray="4 3"
              strokeWidth={1.5}
              dot={false}
              connectNulls={false}
            />
          )}

          {poArrivalWeek && poArrivalOnHand != null && (
            <ReferenceDot
              x={poArrivalWeek}
              y={poArrivalOnHand}
              r={5}
              fill="#16a34a"
              stroke="#fff"
              strokeWidth={1}
              label={{
                value: `PO arrives +${fmtInt(today.suggested_qty)}`,
                position: 'top',
                fontSize: 11,
                fill: '#16a34a',
              }}
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>

      {today.reorder_flag ? (
        <p className="mt-2 text-xs text-muted">
          Ordering today delivers in ~{fmtWeeks(today.lead_time_wk)}.
          {weeksToZero != null && ` Not ordering drops to zero in ~${weeksToZero} wk.`}
        </p>
      ) : (
        <p className="mt-2 text-xs text-muted">
          No alert · current cover ≈ {fmtWeeks(today.weeks_of_cover)}.
        </p>
      )}
    </div>
  );
}
