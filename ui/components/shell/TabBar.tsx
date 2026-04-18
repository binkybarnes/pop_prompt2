'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const TABS = [
  { href: '/alerts', label: 'Reorder Alerts' },
  { href: '/curves', label: 'Demand Curves' },
];

export function TabBar() {
  const pathname = usePathname();
  return (
    <header className="border-b border-border bg-surface">
      <div className="mx-auto flex max-w-[1400px] items-center gap-8 px-6 py-3">
        <div className="text-sm font-semibold tracking-tight text-brand">
          POP Reorder Intelligence
        </div>
        <nav className="flex gap-1">
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
