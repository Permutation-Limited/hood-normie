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
  /** True when the server answered with invented data instead of live accounts. */
  demo: boolean;
  grand_total: string;
  portfolios: Portfolio[];
}

/** One row of the account list, mirroring `//examples:list_accounts`. */
export interface AccountSummary {
  tax_status: string | null;
  account_type: string | null;
  account_number: string | null;
  nickname: string | null;
}

export interface AccountsReport {
  generated_at: string;
  demo: boolean;
  accounts: AccountSummary[];
}

export interface Holding {
  symbol: string;
  quantity: string;
  price: string;
  market_value: string;
}

/** One account's marked holdings, mirroring `//examples:list_holdings`. */
export interface HoldingAccount {
  label: string;
  account_number: string | null;
  cash: string;
  total_value: string;
  positions: Holding[];
}

export interface HoldingsReport {
  generated_at: string;
  demo: boolean;
  grand_total: string;
  accounts: HoldingAccount[];
}

/** One bucket per line of a tax estimate; retirement accounts add to none. */
export interface IncomeTotals {
  short_term: string;
  long_term: string;
  unknown_term: string;
  realized: string;
  qualified: string;
  nonqualified: string;
  unclassified: string;
  dividends: string;
}

export type Term = "short" | "long" | "unknown";

/** One closing trade from Robinhood's realized P&L history. */
export interface Sale {
  date: string;
  symbol: string;
  quantity: string;
  price: string;
  gain: string;
  asset: "equity" | "other";
  term: Term;
  /** How the term was decided; an inference, never a broker-reported fact. */
  reason: string;
}

/** One symbol's reinvested dividends for the year. */
export interface DividendSummary {
  symbol: string;
  payments: number;
  paid: string;
  qualified: string;
  nonqualified: string;
  unclassified: string;
}

export interface IncomeAccount {
  label: string;
  account_number: string;
  tax_advantaged: boolean;
  totals: IncomeTotals;
  sales: Sale[];
  dividends: DividendSummary[];
}

/** A year's realized income, mirroring `//examples/income`. */
export interface IncomeReport {
  generated_at: string;
  demo: boolean;
  year: number;
  taxable_totals: IncomeTotals;
  accounts: IncomeAccount[];
}

export class ApiError extends Error {}

interface FetchOptions {
  demo?: boolean;
  signal?: AbortSignal;
}

async function get<T>(
  path: string,
  options: FetchOptions,
  params: Record<string, string> = {},
): Promise<T> {
  const search = new URLSearchParams(params);
  if (options.demo) {
    search.set("demo", "1");
  }
  const encoded = search.toString();
  const query = encoded ? `?${encoded}` : "";
  const response = await fetch(`${path}${query}`, {
    signal: options.signal ?? null,
  });
  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      body && typeof body === "object" && "error" in body
        ? String((body as { error: unknown }).error)
        : `request failed with status ${response.status}`;
    throw new ApiError(detail);
  }
  return body as T;
}

export async function fetchRebalance(
  options: FetchOptions = {},
): Promise<RebalanceReport> {
  return get<RebalanceReport>("/api/rebalance", options);
}

export async function fetchAccounts(
  options: FetchOptions = {},
): Promise<AccountsReport> {
  return get<AccountsReport>("/api/accounts", options);
}

export async function fetchHoldings(
  options: FetchOptions = {},
): Promise<HoldingsReport> {
  return get<HoldingsReport>("/api/holdings", options);
}

export async function fetchIncome(
  year: number,
  options: FetchOptions = {},
): Promise<IncomeReport> {
  return get<IncomeReport>("/api/income", options, { year: String(year) });
}
