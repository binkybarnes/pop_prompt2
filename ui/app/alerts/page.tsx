import { loadAlertsToday, loadBacktestSummary } from '@/lib/data';
import { AlertsView } from '@/components/list/AlertsView';

export default async function AlertsPage() {
  const [rows, summary] = await Promise.all([
    loadAlertsToday(),
    loadBacktestSummary(),
  ]);

  return <AlertsView rows={rows} summary={summary} />;
}
