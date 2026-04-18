import { promises as fs } from 'node:fs';
import path from 'node:path';
import type {
  AlertRow,
  BacktestSummary,
  LaneCounterfactualFile,
  LaneDemandFile,
  LaneFile,
  LaneIndexRow,
} from './types';

const DATA_DIR = path.join(process.cwd(), 'data');

async function readJson<T>(relativePath: string): Promise<T> {
  const full = path.join(DATA_DIR, relativePath);
  const raw = await fs.readFile(full, 'utf-8');
  return JSON.parse(raw) as T;
}

export async function loadAlertsToday(): Promise<AlertRow[]> {
  return readJson<AlertRow[]>('alerts_today.json');
}

export async function loadLanesIndex(): Promise<LaneIndexRow[]> {
  return readJson<LaneIndexRow[]>('lanes_index.json');
}

export async function loadBacktestSummary(): Promise<BacktestSummary> {
  return readJson<BacktestSummary>('backtest_summary.json');
}

export async function loadLane(slug: string): Promise<LaneFile> {
  return readJson<LaneFile>(`lane/${slug}.json`);
}

export async function loadLaneDemand(slug: string): Promise<LaneDemandFile> {
  return readJson<LaneDemandFile>(`lane/${slug}_demand.json`);
}

export async function loadLaneCounterfactual(
  slug: string
): Promise<LaneCounterfactualFile> {
  return readJson<LaneCounterfactualFile>(`lane/${slug}_counterfactual.json`);
}

export async function listLaneSlugs(): Promise<string[]> {
  const files = await fs.readdir(path.join(DATA_DIR, 'lane'));
  return files
    .filter((f) => f.endsWith('.json') && !f.endsWith('_demand.json') && !f.endsWith('_counterfactual.json'))
    .map((f) => f.replace(/\.json$/, ''));
}
