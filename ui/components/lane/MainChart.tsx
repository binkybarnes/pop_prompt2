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
import type { LaneFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';
import { useMemo } from 'react';

export function MainChart({ lane }: { lane: LaneFile }) {
  const data = useMemo(() => {
    return lane.series.map((r) => {
      const onHandBase = r.on_hand_sim ?? r.on_hand_est;
      return {
        week_start: r.week_start,
        on_hand: r.on_hand_est,
        on_hand_sim: r.on_hand_sim,
        reorder_point: r.reorder_point,
        alert_marker: r.alert_fired ? r.reorder_point : null,
        po_ordered_marker: r.po_ordered ? onHandBase : null,
        po_received_marker: r.po_received ? onHandBase : null,
        stockout_marker: r.fresh_stockout ? 0 : null,
      };
    });
  }, [lane]);

  return (
    <div className="rounded-md border border-border bg-surface p-3">
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={data} margin={{ top: 12, right: 12, left: 12, bottom: 12 }}>
          <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
          <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={32} />
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
          <Line
            type="monotone"
            dataKey="on_hand"
            name="on hand (actual)"
            stroke="#1b2a4a"
            strokeWidth={2}
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="on_hand_sim"
            name="on hand (policy sim)"
            stroke="#16a34a"
            strokeWidth={1.75}
            strokeDasharray="4 3"
            dot={false}
            connectNulls
          />
          <Line
            type="monotone"
            dataKey="reorder_point"
            name="reorder point"
            stroke="#f59e0b"
            strokeDasharray="5 4"
            strokeWidth={1.25}
            dot={false}
            connectNulls
          />
          <Scatter name="alert fired" dataKey="alert_marker" fill="#dc2626" shape="triangle" />
          <Scatter name="PO placed" dataKey="po_ordered_marker" fill="#0891b2" shape="diamond" />
          <Scatter name="PO received" dataKey="po_received_marker" fill="#16a34a" shape="circle" />
          <Scatter name="stockout" dataKey="stockout_marker" fill="#dc2626" shape="cross" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
