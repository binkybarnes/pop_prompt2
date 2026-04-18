'use client';

import Link from 'next/link';
import { useMemo, useState } from 'react';
import type { AlertRow } from '@/lib/types';
import { fmtCases, fmtInt, fmtWeeks, slugOf } from '@/lib/format';
import { Sparkline } from './Sparkline';

type SortKey = 'confidence' | 'weeks_of_cover' | 'suggested_qty' | 'ITEMNMBR' | 'DC';

const CONF_RANK: Record<string, number> = { high: 3, medium: 2, low: 1 };

function applyFilters(
  rows: AlertRow[],
  dc: string,
  confidence: string,
  status: string
): AlertRow[] {
  return rows.filter((r) => {
    if (dc !== 'all' && r.DC !== dc) return false;
    if (confidence !== 'all' && r.confidence !== confidence) return false;
    if (status === 'flagged' && !r.reorder_flag) return false;
    if (status === 'not_flagged' && r.reorder_flag) return false;
    return true;
  });
}

export function AlertTable({
  rows,
  dc,
  confidence,
  status,
}: {
  rows: AlertRow[];
  dc: string;
  confidence: string;
  status: string;
}) {
  const [sortKey, setSortKey] = useState<SortKey>('confidence');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const filtered = useMemo(
    () => applyFilters(rows, dc, confidence, status),
    [rows, dc, confidence, status]
  );
  const sorted = useMemo(() => {
    const copy = [...filtered];
    copy.sort((a, b) => {
      let va: number | string = 0;
      let vb: number | string = 0;
      if (sortKey === 'confidence') {
        va = CONF_RANK[a.confidence] ?? 0;
        vb = CONF_RANK[b.confidence] ?? 0;
      } else if (sortKey === 'weeks_of_cover') {
        va = a.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        vb = b.weeks_of_cover ?? Number.POSITIVE_INFINITY;
      } else if (sortKey === 'suggested_qty') {
        va = a.suggested_qty ?? 0;
        vb = b.suggested_qty ?? 0;
      } else if (sortKey === 'ITEMNMBR') {
        va = a.ITEMNMBR;
        vb = b.ITEMNMBR;
      } else if (sortKey === 'DC') {
        va = a.DC;
        vb = b.DC;
      }
      if (va < vb) return sortDir === 'asc' ? -1 : 1;
      if (va > vb) return sortDir === 'asc' ? 1 : -1;
      return 0;
    });
    if (sortKey === 'confidence') {
      copy.sort((a, b) => {
        const cmp = (CONF_RANK[b.confidence] ?? 0) - (CONF_RANK[a.confidence] ?? 0);
        if (cmp !== 0) return cmp;
        const wa = a.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        const wb = b.weeks_of_cover ?? Number.POSITIVE_INFINITY;
        return wa - wb;
      });
    }
    return copy;
  }, [filtered, sortKey, sortDir]);

  function onSort(k: SortKey) {
    if (k === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else {
      setSortKey(k);
      setSortDir(k === 'confidence' ? 'desc' : 'asc');
    }
  }

  if (sorted.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface p-6 text-center text-sm text-muted">
        No alerts match these filters.
      </div>
    );
  }

  return (
    <div className="overflow-hidden rounded-md border border-border bg-surface">
      <table className="w-full text-sm">
        <thead className="bg-gray-50 text-left text-xs uppercase tracking-wider text-muted">
          <tr>
            <Th onClick={() => onSort('ITEMNMBR')}>SKU</Th>
            <th className="px-3 py-2">Product</th>
            <Th onClick={() => onSort('DC')}>DC</Th>
            <th className="px-3 py-2 text-right">On hand</th>
            <Th onClick={() => onSort('weeks_of_cover')} align="right">Cover</Th>
            <Th onClick={() => onSort('suggested_qty')} align="right">Suggest</Th>
            <Th onClick={() => onSort('confidence')}>Conf</Th>
            <th className="px-3 py-2">Trend</th>
            <th className="px-3 py-2 text-center">Alert</th>
          </tr>
        </thead>
        <tbody>
          {sorted.map((r) => {
            const slug = slugOf(r.ITEMNMBR, r.DC);
            return (
              <tr key={slug} className="border-t border-border hover:bg-gray-50">
                <td className="px-3 py-1.5 font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{r.ITEMNMBR}</Link>
                </td>
                <td className="px-3 py-1.5 text-muted">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    {r.inv_description ?? ''}
                  </Link>
                </td>
                <td className="px-3 py-1.5 font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{r.DC}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtInt(r.on_hand_now)}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtWeeks(r.weeks_of_cover)}</Link>
                </td>
                <td className="px-3 py-1.5 text-right font-mono text-[13px]">
                  <Link href={`/alerts/lane/${slug}`} className="block">{fmtCases(r.suggested_cases)}</Link>
                </td>
                <td className="px-3 py-1.5">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    <ConfidenceBadge c={r.confidence} />
                  </Link>
                </td>
                <td className="px-3 py-1.5">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    <Sparkline values={r.on_hand_sparkline} />
                  </Link>
                </td>
                <td className="px-3 py-1.5 text-center">
                  <Link href={`/alerts/lane/${slug}`} className="block">
                    {r.reorder_flag ? <span className="text-alert">●</span> : <span className="text-muted">○</span>}
                  </Link>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Th({
  children,
  onClick,
  align = 'left',
}: {
  children: React.ReactNode;
  onClick?: () => void;
  align?: 'left' | 'right';
}) {
  return (
    <th
      className={
        'px-3 py-2 ' + (align === 'right' ? 'text-right ' : '') +
        (onClick ? 'cursor-pointer select-none hover:text-fg' : '')
      }
      onClick={onClick}
    >
      {children}
    </th>
  );
}

function ConfidenceBadge({ c }: { c: string }) {
  const color =
    c === 'high' ? 'bg-ok/10 text-ok' :
    c === 'medium' ? 'bg-warn/10 text-warn' :
    'bg-gray-200 text-muted';
  return (
    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${color}`}>{c}</span>
  );
}
