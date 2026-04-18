'use client';

import {
  Area,
  AreaChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { LaneDemandFile } from '@/lib/types';
import { fmtInt, fmtPct } from '@/lib/format';

const CHANNEL_COLORS = {
  MM: '#1b2a4a',
  AM: '#0891b2',
  HF: '#a855f7',
};

export function DemandBreakdown({ demand }: { demand: LaneDemandFile }) {
  if (demand.weekly.length === 0) return null;
  return (
    <section className="space-y-3">
      <h2 className="text-sm font-semibold uppercase tracking-wider text-muted">
        Demand breakdown
      </h2>
      <div className="rounded-md border border-border bg-surface p-3">
        <ResponsiveContainer width="100%" height={180}>
          <AreaChart data={demand.weekly} margin={{ top: 8, right: 12, left: 12, bottom: 8 }}>
            <CartesianGrid stroke="#e5e7eb" strokeDasharray="2 4" />
            <XAxis dataKey="week_start" tick={{ fontSize: 11, fill: '#6b7280' }} minTickGap={32} />
            <YAxis tick={{ fontSize: 11, fill: '#6b7280' }} tickFormatter={(v) => fmtInt(v as number)} width={72} />
            <Tooltip contentStyle={{ fontSize: 12 }} formatter={(v) => fmtInt(Number(v))} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area type="monotone" dataKey="MM" stackId="1" fill={CHANNEL_COLORS.MM} stroke={CHANNEL_COLORS.MM} name="MM" />
            <Area type="monotone" dataKey="AM" stackId="1" fill={CHANNEL_COLORS.AM} stroke={CHANNEL_COLORS.AM} name="AM" />
            <Area type="monotone" dataKey="HF" stackId="1" fill={CHANNEL_COLORS.HF} stroke={CHANNEL_COLORS.HF} name="HF" />
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {demand.top_customers.length > 0 && (
        <div className="rounded-md border border-border bg-surface px-4 py-3">
          <h3 className="text-xs uppercase tracking-wider text-muted">Top customers</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {demand.top_customers.map((c) => (
              <li key={c.custnmbr} className="flex items-center gap-2">
                <span className="font-mono text-[13px] text-muted w-20">{c.custnmbr}</span>
                <span className="flex-1 truncate text-fg">{c.name}</span>
                <span className="w-14 text-right font-mono text-[13px] text-fg">
                  {fmtPct(c.share_pct, 1)}
                </span>
                <div className="w-32 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                  <div className="h-full bg-brand" style={{ width: `${Math.min(100, c.share_pct)}%` }} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
