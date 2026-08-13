/**
 * Client for the local Python API.
 *
 * Every monetary value crosses the wire as a decimal string, exactly as the
 * rebalancer computed it. Parsing to `number` happens only for display, never
 * before a comparison or a total.
 */

export type Action = "BUY" | "SELL" | "HOLD" | "";

export interface Position {
  symbol: string;
  asset_class: string | null;
  quantity: string;
  price: string;
  market_value: string;
}

export interface Account {
  label: string;
  kind: "robinhood" | "external";
  cash: string;
  total_value: string;
  positions: Position[];
}

export interface Recommendation {
  asset_class: string;
  action: Action;
  amount: string;
  current_value: string;
  target_value: string;
  ignored: boolean;
}

export interface Portfolio {
  name: string;
  total_value: string;
  target_cash: string;
  minimum_trade: string;
  accounts: Account[];
  recommendations: Recommendation[];
  unclassified: Position[];
}

export interface RebalanceReport {
  generated_at: string;
  grand_total: string;
  portfolios: Portfolio[];
}

export class ApiError extends Error {}

export async function fetchRebalance(signal?: AbortSignal): Promise<RebalanceReport> {
  const response = await fetch("/api/rebalance", { signal: signal ?? null });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `request failed with status ${response.status}`;
    throw new ApiError(detail);
  }
  return body as RebalanceReport;
}
