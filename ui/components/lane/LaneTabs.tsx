'use client';

import { useState } from 'react';
import type { LaneFile } from '@/lib/types';
import { OperationalChart } from './OperationalChart';
import { LaneChartPanel } from './LaneChartPanel';
import { BacktestTab } from './BacktestTab';

type TabKey = 'prediction' | 'backtest';

export function LaneTabs({ lane }: { lane: LaneFile }) {
  const [active, setActive] = useState<TabKey>('prediction');
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-border">
        {(['prediction', 'backtest'] as TabKey[]).map((k) => (
          <button
            key={k}
            onClick={() => setActive(k)}
            className={
              'px-3 py-1.5 text-sm capitalize ' +
              (active === k
                ? 'border-b-2 border-brand font-semibold text-brand'
                : 'text-muted hover:text-fg')
            }
          >
            {k}
          </button>
        ))}
      </div>
      {active === 'prediction' && <OperationalChart lane={lane} />}
      {active === 'backtest' && (
        <div className="space-y-4">
          <LaneChartPanel lane={lane} />
          <BacktestTab lane={lane} />
        </div>
      )}
    </div>
  );
}
