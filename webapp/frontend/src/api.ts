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
  /** The part of `dividends` estimated from price history: cash payments. */
  estimated_cash: string;
}

/**
 * One IRS estimated-tax period — Jan–Mar, Apr–May, Jun–Aug, Sep–Dec, not
 * calendar quarters — with its own income and the year to date through its end.
 */
export interface TaxPeriod {
  number: number;
  label: string;
  start: string;
  end: string;
  /** Nominal due date; a weekend or holiday moves it to the next business day. */
  due: string;
  totals: IncomeTotals;
  cumulative: IncomeTotals;
}

/** Income by tax rate, after netting capital gains and losses (Schedule D). */
export interface Treatment {
  /** Short-term gains and non-qualified dividends, less `deductible_loss`. */
  ordinary: string;
  /** Long-term gains and qualified dividends. */
  preferential: string;
  /** Net capital loss applied against ordinary income, up to $3,000. */
  deductible_loss: string;
  /** Net capital loss beyond the limit, carried into next year. */
  carryforward: string;
}

/**
 * What is known, and the two extremes for unresolved amounts: unknown-term
 * gains and unclassified dividends all at ordinary rates, or all preferential.
 */
export interface TreatmentRange {
  known: Treatment;
  all_ordinary: Treatment;
  all_preferential: Treatment;
  unresolved_gains: string;
  unresolved_dividends: string;
}

export interface TaxablePeriod extends TaxPeriod {
  /** This period's share: the change in the year-to-date treatment. */
  treatment: TreatmentRange;
  cumulative_treatment: TreatmentRange;
}

export interface Replacement {
  date: string;
  account_label: string;
  tax_advantaged: boolean;
  quantity: string;
}

/** A loss sale with purchases of the same symbol within 30 days. */
export interface WashSale {
  account_label: string;
  date: string;
  symbol: string;
  quantity: string;
  loss: string;
  replaced: string;
  /** The loss share the replacements cover, as a positive amount. */
  disallowed: string;
  /** The part replaced in a tax-advantaged account: lost for good. */
  permanent: string;
  replacements: Replacement[];
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
  /** Cash payments, estimated; the rest of `paid` was reinvested and exact. */
  estimated_cash: string;
}

export interface IncomeAccount {
  label: string;
  account_number: string;
  tax_advantaged: boolean;
  totals: IncomeTotals;
  periods: TaxPeriod[];
  sales: Sale[];
  dividends: DividendSummary[];
}

/** A year's realized income, mirroring `//examples/income`. */
export interface IncomeReport {
  generated_at: string;
  demo: boolean;
  year: number;
  taxable_totals: IncomeTotals;
  taxable_treatment: TreatmentRange;
  taxable_periods: TaxablePeriod[];
  carryover_short: string;
  carryover_long: string;
  wash_sales: WashSale[];
  possibly_disallowed: string;
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
  // URLSearchParams when a key repeats, as `account` does for lots.
  params: Record<string, string> | URLSearchParams = {},
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

/** Totals over holdings with both a price and a cost basis. */
export interface UnrealizedTotals {
  market_value: string;
  cost_basis: string;
  unrealized: string;
  /** Unrealized gain as a fraction of cost; null without a positive cost. */
  return_rate: string | null;
  /** Holdings left out of the sums for want of a price or basis. */
  incomplete: number;
  /** The gain split by Robinhood's lot terms. */
  short_term: string;
  long_term: string;
  /** Gain on holdings without lot bases (average cost), so no term. */
  unknown_term: string;
}

export type BasisSource = "tax lots" | "average cost" | "unavailable";

export interface UnrealizedHolding {
  symbol: string;
  quantity: string;
  price: string | null;
  market_value: string | null;
  cost_basis: string | null;
  unrealized: string | null;
  return_rate: string | null;
  /** "tax lots" unless a lot's basis is pending; then Robinhood's average cost. */
  basis_source: BasisSource;
  short_term: string;
  long_term: string;
  unknown_term: string;
  /** The earliest date a short-term lot goes long-term. */
  next_long_term: string | null;
  lot_count: number;
  /** Where the lots live; pass these to `fetchLots` to list them. */
  account_numbers: string[];
}

export type LotTerm = "short" | "long" | "unknown";

export interface Lot {
  account_number: string;
  acquired: string | null;
  quantity: string;
  cost_basis: string | null;
  market_value: string | null;
  unrealized: string | null;
  /** Robinhood's own term, which counts inherited wash-sale holding periods. */
  term: LotTerm;
  /** When a short-term lot goes long-term, counted from its purchase date. */
  long_term_on: string | null;
}

export interface HoldingLots {
  generated_at: string;
  demo: boolean;
  symbol: string;
  price: string | null;
  lots: Lot[];
}

export interface UnrealizedAccount {
  label: string;
  account_number: string;
  tax_advantaged: boolean;
  totals: UnrealizedTotals;
  holdings: UnrealizedHolding[];
}

/** Unrealized gains, mirroring `//examples/unrealized`. */
export interface UnrealizedReport {
  generated_at: string;
  demo: boolean;
  taxable_totals: UnrealizedTotals;
  /** Taxable holdings merged by symbol across accounts. */
  combined: UnrealizedHolding[];
  accounts: UnrealizedAccount[];
}

export async function fetchUnrealized(
  options: FetchOptions = {},
): Promise<UnrealizedReport> {
  return get<UnrealizedReport>("/api/unrealized", options);
}

/** One holding's open lots, fetched only when its row is expanded. */
export async function fetchLots(
  symbol: string,
  accounts: readonly string[],
  options: FetchOptions = {},
): Promise<HoldingLots> {
  const params = new URLSearchParams({ symbol });
  for (const account of accounts) {
    params.append("account", account);
  }
  return get<HoldingLots>("/api/lots", options, params);
}
