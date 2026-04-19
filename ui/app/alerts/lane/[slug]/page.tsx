import Link from 'next/link';
import { notFound } from 'next/navigation';
import {
  loadLane,
  loadLaneDemand,
  loadLanesIndex,
  listLaneSlugs,
} from '@/lib/data';
import { LaneHeader } from '@/components/lane/LaneHeader';
import { LaneTabs } from '@/components/lane/LaneTabs';
import { SidePanel } from '@/components/lane/SidePanel';
import { DemandBreakdown } from '@/components/lane/DemandBreakdown';

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
  let lane, demand;
  try {
    [lane, demand] = await Promise.all([
      loadLane(slug),
      loadLaneDemand(slug),
    ]);
  } catch {
    notFound();
  }

  let laneSummary;
  try {
    const lanesIdx = await loadLanesIndex();
    laneSummary = lanesIdx.find((l) => l.sku === lane.sku && l.dc === lane.dc);
  } catch {
    laneSummary = undefined;
  }

  return (
    <div className="space-y-4">
      <Link href="/alerts" className="text-sm text-muted hover:text-fg">
        ← Back to alerts
      </Link>
      <LaneHeader lane={lane} />
      <div className="flex gap-4">
        <div className="flex-1 min-w-0">
          <LaneTabs lane={lane} />
        </div>
        <SidePanel lane={lane} laneSummary={laneSummary} />
      </div>
      <DemandBreakdown demand={demand} />
    </div>
  );
}
