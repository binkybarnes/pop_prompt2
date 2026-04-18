'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { ChartTab } from './ChartTab';
import { BacktestTab } from './BacktestTab';
import { StrategyTab } from './StrategyTab';

type TabKey = 'chart' | 'backtest' | 'strategy';

export function LaneTabs({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [active, setActive] = useState<TabKey>('chart');
  return (
    <div className="space-y-3">
      <div className="flex gap-1 border-b border-border">
        {(['chart', 'backtest', 'strategy'] as TabKey[]).map((k) => (
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
      {active === 'chart' && <ChartTab lane={lane} counterfactual={counterfactual} />}
      {active === 'backtest' && <BacktestTab lane={lane} />}
      {active === 'strategy' && <StrategyTab lane={lane} counterfactual={counterfactual} />}
    </div>
  );
}
