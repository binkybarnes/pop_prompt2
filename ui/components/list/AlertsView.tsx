'use client';

import { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import type { AlertRow, BacktestSummary } from '@/lib/types';
import { AlertTable } from './AlertTable';
import { FilterChips } from './FilterChips';
import { SummaryStats } from './SummaryStats';

function AlertsViewInner({
  rows,
  summary,
}: {
  rows: AlertRow[];
  summary: BacktestSummary;
}) {
  const sp = useSearchParams();
  const dc = sp.get('dc') ?? 'all';
  const confidence = sp.get('confidence') ?? 'all';
  const status = sp.get('status') ?? 'flagged';

  return (
    <div className="space-y-4">
      <FilterChips dc={dc} confidence={confidence} status={status} />
      <SummaryStats rows={rows} dc={dc} confidence={confidence} status={status} summary={summary} />
      <AlertTable rows={rows} dc={dc} confidence={confidence} status={status} />
    </div>
  );
}

export function AlertsView({
  rows,
  summary,
}: {
  rows: AlertRow[];
  summary: BacktestSummary;
}) {
  return (
    <Suspense fallback={<div className="text-muted">Loading alerts…</div>}>
      <AlertsViewInner rows={rows} summary={summary} />
    </Suspense>
  );
}
