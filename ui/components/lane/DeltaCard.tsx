import type { LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function DeltaCard({
  counterfactual,
  overlay,
}: {
  counterfactual: LaneCounterfactualFile;
  overlay: 'none' | 'mean' | 'p90';
}) {
  if (overlay === 'none') return null;
  const t = counterfactual.trough_delta;
  const chosen = overlay === 'mean' ? t.mean : t.p90;
  if (t.actual === null || chosen === null) return null;
  const improvement = chosen - t.actual;

  return (
    <div className="rounded-md border border-border bg-surface px-4 py-3 text-sm">
      <div className="flex flex-wrap items-baseline gap-4">
        <span>
          <span className="text-muted">Actual trough:</span>{' '}
          <span className="font-mono font-semibold text-alert">{fmtInt(t.actual)}</span>
        </span>
        <span>
          <span className="text-muted">Mean-followed:</span>{' '}
          <span className={'font-mono font-semibold ' + (overlay === 'mean' ? 'text-ok' : 'text-muted')}>
            {fmtInt(t.mean)}
          </span>
        </span>
        <span>
          <span className="text-muted">P90-followed:</span>{' '}
          <span className={'font-mono font-semibold ' + (overlay === 'p90' ? 'text-ok' : 'text-muted')}>
            {fmtInt(t.p90)}
          </span>
        </span>
        <span className="ml-auto">
          <span className="text-muted">Improvement:</span>{' '}
          <span className={'font-mono font-semibold ' + (improvement > 0 ? 'text-ok' : 'text-alert')}>
            {improvement > 0 ? '+' : ''}{fmtInt(improvement)}
          </span>
          <span className="ml-1 text-muted">units</span>
        </span>
      </div>
    </div>
  );
}
