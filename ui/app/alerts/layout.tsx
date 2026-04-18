import { TabBar } from '@/components/shell/TabBar';

export default function AlertsLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
      <TabBar />
      <main className="mx-auto max-w-[1400px] px-6 py-6">{children}</main>
    </>
  );
}
