'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { useCallback } from 'react';

type ChipDef = { key: string; label: string; options: { value: string; label: string }[] };

const CHIPS: ChipDef[] = [
  {
    key: 'dc',
    label: 'DC',
    options: [
      { value: 'all', label: 'All' },
      { value: 'SF', label: 'SF' },
      { value: 'NJ', label: 'NJ' },
      { value: 'LA', label: 'LA' },
    ],
  },
  {
    key: 'confidence',
    label: 'Confidence',
    options: [
      { value: 'all', label: 'All' },
      { value: 'high', label: 'High' },
      { value: 'medium', label: 'Medium' },
      { value: 'low', label: 'Low' },
    ],
  },
  {
    key: 'status',
    label: 'Status',
    options: [
      { value: 'flagged', label: 'Flagged only' },
      { value: 'not_flagged', label: 'Not flagged' },
      { value: 'all', label: 'All' },
    ],
  },
];

export function FilterChips({
  dc,
  confidence,
  status,
}: {
  dc: string;
  confidence: string;
  status: string;
}) {
  const router = useRouter();
  const sp = useSearchParams();
  const current: Record<string, string> = { dc, confidence, status };

  const update = useCallback(
    (key: string, value: string) => {
      const next = new URLSearchParams(sp.toString());
      const defaults: Record<string, string> = { dc: 'all', confidence: 'all', status: 'flagged' };
      if (value === defaults[key]) next.delete(key);
      else next.set(key, value);
      const qs = next.toString();
      router.push(qs ? `/alerts?${qs}` : '/alerts');
    },
    [router, sp]
  );

  return (
    <div className="flex flex-wrap items-center gap-2 text-sm">
      {CHIPS.map((chip) => (
        <div key={chip.key} className="flex items-center gap-1">
          <span className="text-xs uppercase tracking-wider text-muted">{chip.label}</span>
          <div className="flex rounded-md border border-border bg-surface">
            {chip.options.map((opt) => {
              const active = current[chip.key] === opt.value;
              return (
                <button
                  key={opt.value}
                  onClick={() => update(chip.key, opt.value)}
                  className={
                    'px-2.5 py-1 text-xs first:rounded-l-md last:rounded-r-md ' +
                    (active ? 'bg-brand text-white' : 'hover:bg-gray-50')
                  }
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
