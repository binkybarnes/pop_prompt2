'use client';

import type { LaneFile } from '@/lib/types';
import { MainChart } from './MainChart';

export function LaneChartPanel({ lane }: { lane: LaneFile }) {
  const regime = lane.today.regime ?? null;
  const trend = lane.today.trend_ratio ?? null;
  return (
    <div className="space-y-3">
      <div className="rounded-md border border-border bg-gray-50 px-4 py-2 text-xs text-muted">
        Policy: trend-aware + empirical-p99 SS + 70% hybrid floor.
        {regime && (
          <>
            {' '}Current regime: <span className="font-mono text-fg">{regime}</span>
            {trend !== null && (
              <> (trend ratio <span className="font-mono text-fg">{trend.toFixed(2)}</span>)</>
            )}.
          </>
        )}
      </div>
      <MainChart lane={lane} />
    </div>
  );
}
