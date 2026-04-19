'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { ChartTab } from './ChartTab';
import { BacktestTab } from './BacktestTab';
import { StrategyTab } from './StrategyTab';

type TabKey = 'historical chart' | 'backtest stats' | 'strategy comparison';

export function LaneTabs({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [active, setActive] = useState<TabKey>('historical chart');
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-border">
        {(['historical chart', 'backtest stats', 'strategy comparison'] as TabKey[]).map((k) => (
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
      {active === 'historical chart' && <ChartTab lane={lane} counterfactual={counterfactual} />}
      {active === 'backtest stats' && <BacktestTab lane={lane} />}
      {active === 'strategy comparison' && <StrategyTab lane={lane} counterfactual={counterfactual} />}
    </div>
  );
}
