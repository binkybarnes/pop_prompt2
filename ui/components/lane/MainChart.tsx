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
    return lane.series.map((r, i, arr) => {
      const onHandBase = r.on_hand_sim ?? r.on_hand_est;
      const prevOnHand = i > 0 ? arr[i - 1].on_hand_est : onHandBase;
      
      return {
        week_start: r.week_start,
        on_hand: r.on_hand_est,
        on_hand_sim: r.on_hand_sim,
        reorder_point: r.reorder_point,
        alert_marker: r.alert_fired ? r.reorder_point : null,
        po_ordered_marker: r.po_ordered ? onHandBase : null,
        po_received_marker: r.po_received ? onHandBase : null,
        stockout_marker: (typeof r.on_hand_est === 'number' && typeof prevOnHand === 'number' && r.on_hand_est <= 0 && prevOnHand > 0) ? 0 : null,
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
            contentStyle={{ fontSize: 12, borderRadius: '6px', border: '1px solid #e5e7eb' }}
            formatter={(v, name) => {
              if (v === null || v === undefined) return ['—', name as string];
              const num = typeof v === 'number' ? v : Number(v);
              if (Number.isNaN(num)) return ['—', name as string];
              return [fmtInt(num), name as string];
            }}
          />
          <Legend
            verticalAlign="bottom"
            content={(props: any) => {
              const { payload } = props;
              if (!payload) return null;
              
              const lines = payload.filter((entry: any) => entry.type === 'line');
              const points = payload.filter((entry: any) => entry.type !== 'line');

              return (
                <div className="mt-3 flex flex-col items-center gap-2.5 text-xs text-muted">
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/50">Trajectories</span>
                    <div className="flex gap-5">
                      {lines.map((entry: any, index: number) => (
                        <div key={`line-${index}`} className="flex items-center gap-1.5">
                          <svg width="16" height="6" className="inline-block overflow-visible">
                            <line 
                              x1="0" y1="3" x2="16" y2="3" 
                              stroke={entry.color} 
                              strokeWidth={entry.payload?.strokeWidth || 2} 
                              strokeDasharray={entry.payload?.strokeDasharray} 
                            />
                          </svg>
                          <span>{entry.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                  <div className="flex items-center gap-4">
                    <span className="text-[10px] font-bold uppercase tracking-wider text-fg/50 flex-shrink-0">Events</span>
                    <div className="flex gap-5">
                      {points.map((entry: any, index: number) => (
                        <div key={`point-${index}`} className="flex items-center gap-1.5">
                          <svg width="10" height="10" className="inline-block overflow-visible" fill={entry.color}>
                            {entry.type === 'diamond' ? (
                              <polygon points="5,0 10,5 5,10 0,5" />
                            ) : (
                              <circle cx="5" cy="5" r="4.5" />
                            )}
                          </svg>
                          <span>{entry.value}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="on_hand"
            name="on hand (actual)"
            stroke="#1b2a4a"
            strokeWidth={2}
            dot={false}
            legendType="line"
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
            legendType="line"
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
            legendType="line"
            connectNulls
          />
          <Scatter name="PO placed" dataKey="po_ordered_marker" fill="#0891b2" shape="diamond" legendType="diamond" />
          <Scatter name="PO received" dataKey="po_received_marker" fill="#16a34a" shape="circle" legendType="circle" />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}
