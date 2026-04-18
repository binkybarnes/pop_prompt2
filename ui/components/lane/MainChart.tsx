'use client';

import {
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';
import { useMemo } from 'react';

type Strategy = 'mean' | 'p90';
type Overlay = 'none' | 'mean' | 'p90';

export function MainChart({
  lane,
  strategy,
  overlay,
  counterfactual,
}: {
  lane: LaneFile;
  strategy: Strategy;
  overlay: Overlay;
  counterfactual: LaneCounterfactualFile;
}) {
  const data = useMemo(() => {
    const cfByWeek = new Map(counterfactual.series.map((r) => [r.week_start, r]));
    const posByWeek = new Map<string, { strategy: string; qty: number }>();
    for (const po of counterfactual.simulated_pos) {
      if (overlay !== 'none' && po.strategy === overlay) {
        const existing = posByWeek.get(po.arrival_week);
        posByWeek.set(po.arrival_week, {
          strategy: po.strategy,
          qty: (existing?.qty ?? 0) + po.qty,
        });
      }
    }
    return lane.series.map((r) => {
      const cf = cfByWeek.get(r.week_start);
      const alertFired = strategy === 'mean' ? r.alert_fired_mean : r.alert_fired_p90;
      const reorderPoint = strategy === 'mean' ? r.reorder_point_mean : r.reorder_point_p90;
      const po = posByWeek.get(r.week_start);
      return {
        week_start: r.week_start,
        on_hand: r.on_hand_est,
        reorder_point: reorderPoint,
        alert_marker: alertFired ? reorderPoint : null,
        stockout_marker: r.fresh_stockout && r.on_hand_est !== null ? 0 : null,
        mean_followed: cf?.mean_followed ?? null,
        p90_followed: cf?.p90_followed ?? null,
        po_marker: po ? (overlay === 'mean' ? cf?.mean_followed : cf?.p90_followed) ?? null : null,
      };
    });
  }, [lane, strategy, overlay, counterfactual]);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <ResponsiveContainer width="100%" height={360}>
        <ComposedChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
          <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={32} />
          <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => fmtInt(v as number)} width={72} />
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
          <Line type="monotone" dataKey="on_hand" name="on_hand (actual)" stroke="#1b2a4a" strokeWidth={2} dot={false} connectNulls />
          <Line
            type="monotone"
            dataKey="reorder_point"
            name={`reorder_point (${strategy})`}
            stroke="#f59e0b"
            strokeDasharray="5 4"
            strokeWidth={1.5}
            dot={false}
            connectNulls
          />
          {overlay !== 'none' && (
            <Line
              type="monotone"
              dataKey={overlay === 'mean' ? 'mean_followed' : 'p90_followed'}
              name={overlay === 'mean' ? 'mean-followed' : 'p90-followed'}
              stroke={overlay === 'mean' ? '#16a34a' : '#0891b2'}
              strokeWidth={1.5}
              strokeDasharray="2 2"
              dot={false}
              connectNulls
            />
          )}
          <Scatter name="alert fired" dataKey="alert_marker" fill="#dc2626" shape="triangle" />
          <Scatter name="stockout" dataKey="stockout_marker" fill="#dc2626" shape="cross" />
          {overlay !== 'none' && (
            <Scatter
              name={`simulated PO (${overlay})`}
              dataKey="po_marker"
              fill={overlay === 'mean' ? '#16a34a' : '#0891b2'}
              shape="circle"
            />
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
