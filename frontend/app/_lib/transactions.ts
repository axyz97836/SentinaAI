export type Numeric = number | string;
export type RiskBand = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Transaction = {
  id: string; external_id: string; customer_ref: string; occurred_at: string;
  amount: Numeric; currency: string; merchant_category: string; country_code: string;
  channel: string; device_ref: string | null; source: string; ingested_at: string;
};
export type TransactionRow = Transaction & { risk_score: Numeric; risk_band: RiskBand; model_version_id: string };
export type TransactionList = { items: TransactionRow[]; next_cursor: string | null };
export type TransactionDetail = {
  transaction: Transaction;
  score: { id: string; model_version_id: string; risk_score: Numeric; risk_band: RiskBand; scored_at: string };
  alert_id: string | null; case_id: string | null;
};
export type Explanation = {
  model_version_id: string; explanation_status: "COMPLETE" | "PARTIAL";
  component_contributions: Record<"supervised" | "anomaly" | "rules", { value: Numeric; weight: Numeric; risk_points: Numeric }>;
  rule_evaluations: { code: string; status: string; [key: string]: unknown }[];
  supervised_attribution: {
    available: boolean; reason?: string; method?: string; units?: string;
    base_value?: Numeric; model_output?: Numeric; remaining_features_contribution?: Numeric;
    top_features: { feature: string; transformed_feature: string; contribution: Numeric }[];
    limitation?: string;
  };
  settings_snapshot: Record<string, unknown>; caveat: string; limitations: string[];
};
export type IngestionJob = {
  job_id: string; dataset_id: string; type: string; status: string; total_rows: number | null;
  processed_rows: number; failed_rows: number; attempt_count: number;
  progress_phase: string; error_code: string | null; error_message: string | null;
  cleanup_pending: boolean; errors: { row_number: number; code: string; summary: string }[];
};
export const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
export const number = (value: Numeric, digits = 4) => new Intl.NumberFormat("en", { maximumFractionDigits: digits }).format(Number(value));
export const money = (value: Numeric, currency: string) => new Intl.NumberFormat("en", { style: "currency", currency, currencyDisplay: "code", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(Number(value));
export const timestamp = (value: string) => new Intl.DateTimeFormat("en-GB", { dateStyle: "medium", timeStyle: "short", timeZone: "UTC" }).format(new Date(value)) + " UTC";
export const readable = (value: string) => value.toLowerCase().replaceAll("_", " ");
