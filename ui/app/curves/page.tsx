import { TabBar } from '@/components/shell/TabBar';

export default function CurvesPage() {
  return (
    <>
      <TabBar />
      <main className="mx-auto max-w-[1400px] px-6 py-16 text-center">
        <h1 className="text-2xl font-semibold text-brand">Demand Curves</h1>
        <p className="mt-3 text-muted">
          Coming soon — F2 per-SKU × channel elasticity curves, scatter, and
          price predictor.
        </p>
      </main>
    </>
  );
}
