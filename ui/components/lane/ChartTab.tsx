import type { LaneFile, LaneCounterfactualFile } from '@/lib/types';
import { LaneChartPanel } from './LaneChartPanel';

export function ChartTab({
  lane,
  counterfactual,
}: {
  lane: LaneFile;
  counterfactual: LaneCounterfactualFile;
}) {
  return <LaneChartPanel lane={lane} counterfactual={counterfactual} />;
}
