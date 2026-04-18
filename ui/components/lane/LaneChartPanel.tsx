'use client';

import { useState } from 'react';
import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { MainChart } from './MainChart';
import { DeltaCard } from './DeltaCard';
import { NarrativeBanner } from './NarrativeBanner';

type Strategy = 'mean' | 'p90';
type Overlay = 'none' | 'mean' | 'p90';

export function LaneChartPanel({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  const [strategy, _setStrategy] = useState<Strategy>('mean');
  const [overlay, setOverlay] = useState<Overlay>('none');

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-xs">
        <span className="text-muted">Overlay:</span>
        {(['none', 'mean', 'p90'] as Overlay[]).map((opt) => (
          <button
            key={opt}
            onClick={() => setOverlay(opt)}
            className={
              'rounded border px-2 py-1 ' +
              (overlay === opt
                ? 'border-brand bg-brand text-white'
                : 'border-border bg-surface hover:bg-gray-50')
            }
          >
            {opt === 'none' ? 'Actual only' : opt === 'mean' ? '+ Mean' : '+ P90'}
          </button>
        ))}
      </div>
      <NarrativeBanner counterfactual={counterfactual} overlay={overlay} />
      <MainChart lane={lane} strategy={strategy} overlay={overlay} counterfactual={counterfactual} />
      <DeltaCard counterfactual={counterfactual} overlay={overlay} />
    </div>
  );
}
