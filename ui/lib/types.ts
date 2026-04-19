export type DC = 'SF' | 'NJ' | 'LA';
export type Confidence = 'high' | 'medium' | 'low';
export type Channel = 'MM' | 'AM' | 'HF';
export type Regime = 'declining' | 'growing' | 'stable';

export interface AlertRow {
  ITEMNMBR: string;
  DC: DC;
  inv_description: string | null;
  available_now: number | null;
  on_hand_now: number | null;
  run_rate_wk: number | null;
  std_wk: number | null;
  n_clean_weeks: number | null;
  case_pack: number | null;
  lead_time_wk: number | null;
  lead_time_source: 'po_history' | 'parsed' | 'default' | null;
  safety_stock: number | null;
  reorder_point: number | null;
  weeks_of_cover: number | null;
  reorder_flag: boolean;
  suggested_qty: number | null;
  suggested_cases: number | null;
  confidence: Confidence;
  on_hand_sparkline: (number | null)[];
  [key: string]: unknown;
}

export interface LaneIndexRow {
  sku: string;
  dc: DC;
  sku_desc: string;
  brand: string;
  fresh_rate: number;
  n_weeks: number;
  n_alerts: number;
  n_fresh: number;
  today_flag: boolean;
  today_confidence: Confidence;
}

export interface LaneSeriesRow {
  week_start: string;
  on_hand_est: number | null;
  on_hand_sim: number | null;
  reorder_point: number | null;
  run_rate_wk: number | null;
  regime: Regime | null;
  alert_fired: boolean;
  po_ordered: boolean;
  po_received: boolean;
  fresh_stockout: boolean;
  weeks_until_stockout: number | null;
}

export interface SimulatedPO {
  order_week: string;
  arrival_week: string;
  qty: number;
}

export interface LaneToday {
  reorder_flag: boolean;
  confidence: Confidence;
  on_hand: number | null;
  available: number | null;
  reorder_point: number | null;
  run_rate_wk: number | null;
  lead_time_wk: number | null;
  lead_time_source: string | null;
  suggested_qty: number | null;
  suggested_cases: number | null;
  weeks_of_cover: number | null;
  safety_stock: number | null;
  std_wk: number | null;
  n_clean_weeks: number | null;
  regime?: Regime | null;
  trend_ratio?: number | null;
}

export interface LaneMetadata {
  sku_desc: string;
  case_pack: number | null;
  vendor: string;
  country: string;
}

export interface LaneFile {
  sku: string;
  dc: DC;
  series: LaneSeriesRow[];
  simulated_pos: SimulatedPO[];
  today: LaneToday;
  metadata: LaneMetadata;
}

export interface DemandWeek {
  week_start: string;
  MM: number;
  AM: number;
  HF: number;
}

export interface DemandCustomer {
  custnmbr: string;
  name: string;
  share_pct: number;
  qty: number;
}

export interface LaneDemandFile {
  sku: string;
  dc: DC;
  weekly: DemandWeek[];
  top_customers: DemandCustomer[];
}

export interface BacktestSummary {
  method?: string;
  total_lanes?: number;
  total_alerts_today?: number;
  total_alerts_high_conf?: number;
  total_alerts_med_conf?: number;
  total_alerts_low_conf?: number;
  [key: string]: unknown;
}
