import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneCounterfactual,
  loadLaneDemand,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';
import { LaneChartPanel } from '@/components/lane/LaneChartPanel';

export async function generateStaticParams() {
  const slugs = await listLaneSlugs();
  return slugs.map((slug) => ({ slug }));
}

export default async function LanePage({
  params,
}: {
  params: Promise<{ slug: string }>;
}) {
  const { slug } = await params;
  let lane, demand, cf;
  try {
    [lane, demand, cf] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
      loadLaneCounterfactual(slug),
    ]);
  } catch {
    notFound();
  }

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      <LaneChartPanel lane={lane} counterfactual={cf} />
      <pre className="text-xs text-muted">demand weeks: {demand.weekly.length}</pre>
    </div>
  );
}
