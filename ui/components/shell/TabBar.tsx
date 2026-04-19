'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/alerts', label: 'Reorder Alerts' },
];

export function TabBar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-6 py-3">
        <div className="flex items-center gap-4 pr-6 border-r border-border/60">
          <div className="bg-brand rounded-md p-1.5 flex items-center justify-center shadow-sm">
            <img src="/logo.avif" alt="POP" className="h-6 w-auto object-contain" />
          </div>
          <div className="flex flex-col">
            <span className="text-[15px] font-bold tracking-tight text-slate-900 leading-none">
              Supply Chain Monitor
            </span>
          </div>
        </div>
        <nav className="flex gap-2">
          {TABS.map((t) => {
            const active = pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={
                  'rounded-md px-3 py-1.5 text-sm ' +
                  (active
                    ? 'bg-brand text-white'
                    : 'text-muted hover:bg-gray-100')
                }
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
      </div>
    </header>
  );
}
