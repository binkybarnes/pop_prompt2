import type { LaneCounterfactualFile } from '@/lib/types';
import { fmtInt } from '@/lib/format';

export function NarrativeBanner({
  counterfactual,
  overlay,
}: {
  counterfactual: LaneCounterfactualFile;
  overlay: 'none' | 'mean' | 'p90';
}) {
  const n = counterfactual.narrative;
  const t = counterfactual.trough_delta;
  let text: string;
  if (n) {
    text =
      overlay === 'none' ? n.actual_only :
      overlay === 'mean' ? n.plus_mean :
      n.plus_p90;
  } else {
    if (overlay === 'none') {
      text = t.actual !== null
        ? `Actual trough: ${fmtInt(t.actual)} units.`
        : 'No inventory trough recorded for this lane.';
    } else {
      const chosen = overlay === 'mean' ? t.mean : t.p90;
      const improvement = (chosen !== null && t.actual !== null) ? chosen - t.actual : null;
      text = improvement !== null
        ? `Following the ${overlay} strategy changes the trough by ${fmtInt(improvement)} units (${improvement > 0 ? 'improvement' : 'shortfall'}).`
        : `${overlay} strategy trajectory shown above.`;
    }
  }
  return (
    <div className="rounded-md border border-border bg-gray-50 px-4 py-2 text-sm italic text-fg">
      {text}
    </div>
  );
}
