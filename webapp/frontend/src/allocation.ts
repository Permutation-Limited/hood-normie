/**
 * Slices for the rebalance page's allocation donuts.
 *
 * Pure data: which entities get a slice, how big, and what color. The drawing
 * is `components/AllocationDonut.tsx`. Values are parsed to `number` here only
 * to size arcs; every label still shows the API's decimal string.
 */
import type { Account, Recommendation } from "./api";

/** The class a position with no configured mapping is drawn under. */
export const UNCLASSIFIED = "unclassified";
/** The rebalancer's own name for the cash line of a plan. */
export const CASH = "cash";
/** Where the smallest symbols of a drill-down fold once there are too many. */
export const OTHER = "other";

/**
 * At most this many slices per donut. Past it, adjacent hues stop being
 * distinguishable, so the smallest entries fold into one "other" slice.
 */
export const MAX_SLICES = 8;

export interface Slice {
  key: string;
  label: string;
  /** Exact decimal string, for display. */
  amount: string;
  /** Parsed `amount`, for geometry only. */
  value: number;
  /** Index into the categorical palette, or null for the neutral color. */
  slot: number | null;
  /** Whether clicking the slice opens the holdings beneath it. */
  drillable: boolean;
}

/** A value a donut cannot draw: a margin balance, or a negative cash target. */
export interface Excluded {
  label: string;
  amount: string;
}

export interface Allocation {
  slices: Slice[];
  excluded: Excluded[];
}

/** Adds two decimal strings exactly, at whatever scale they carry. */
export function addDecimal(a: string, b: string): string {
  const parse = (value: string): { digits: bigint; scale: number } => {
    const text = value.trim();
    const negative = text.startsWith("-");
    const [whole = "0", fraction = ""] = text.replace(/^[-+]/, "").split(".");
    const digits = BigInt((whole || "0") + fraction);
    return { digits: negative ? -digits : digits, scale: fraction.length };
  };
  const left = parse(a);
  const right = parse(b);
  const scale = Math.max(left.scale, right.scale);
  const sum =
    left.digits * 10n ** BigInt(scale - left.scale) +
    right.digits * 10n ** BigInt(scale - right.scale);
  const sign = sum < 0n ? "-" : "";
  const text = (sum < 0n ? -sum : sum).toString().padStart(scale + 1, "0");
  return scale === 0
    ? `${sign}${text}`
    : `${sign}${text.slice(0, -scale)}.${text.slice(-scale)}`;
}

/**
 * Fixes each class's color for a whole portfolio: the plan's order, then
 * unclassified. Every donut of the portfolio (current, target, each account)
 * reads from this, so a class keeps its color when a scope drops other classes.
 * Cash is left out; it draws in the neutral color.
 */
export function classSlots(recommendations: readonly Recommendation[]): Map<string, number> {
  const slots = new Map<string, number>();
  for (const name of [...recommendations.map((item) => item.asset_class), UNCLASSIFIED]) {
    if (name !== CASH && !slots.has(name)) {
      slots.set(name, slots.size);
    }
  }
  return slots;
}

function classSlot(slots: ReadonlyMap<string, number>, name: string): number | null {
  if (name === CASH) {
    return null;
  }
  // A class missing from the plan still gets a stable slot after the known ones.
  return slots.get(name) ?? slots.size;
}

/** Splits entries into drawable slices and the negatives a donut cannot show. */
function partition(
  entries: Iterable<[string, string]>,
  slice: (key: string, amount: string, value: number) => Slice,
  label: (key: string) => string,
): Allocation {
  const slices: Slice[] = [];
  const excluded: Excluded[] = [];
  for (const [key, amount] of entries) {
    const value = Number(amount);
    if (value > 0) {
      slices.push(slice(key, amount, value));
    } else if (value < 0) {
      excluded.push({ label: label(key), amount });
    }
  }
  return { slices: slices.sort((a, b) => b.value - a.value), excluded };
}

/** What the accounts hold now, by asset class, cash included. */
export function currentByClass(
  accounts: readonly Account[],
  slots: ReadonlyMap<string, number>,
): Allocation {
  const totals = new Map<string, string>();
  const add = (key: string, amount: string): void => {
    totals.set(key, addDecimal(totals.get(key) ?? "0", amount));
  };
  for (const account of accounts) {
    for (const position of account.positions) {
      add(position.asset_class ?? UNCLASSIFIED, position.market_value);
    }
    add(CASH, account.cash);
  }
  return partition(
    totals,
    (key, amount, value) => ({
      key,
      label: key,
      amount,
      value,
      slot: classSlot(slots, key),
      drillable: key !== CASH,
    }),
    (key) => key,
  );
}

/** The plan's target for each class: where the portfolio ends up. */
export function targetByClass(
  recommendations: readonly Recommendation[],
  slots: ReadonlyMap<string, number>,
): Allocation {
  return partition(
    recommendations.map((item) => [item.asset_class, item.target_value]),
    (key, amount, value) => ({
      key,
      label: key,
      amount,
      value,
      slot: classSlot(slots, key),
      drillable: false,
    }),
    (key) => key,
  );
}

/**
 * One class's holdings, by symbol, summed across the accounts. Beyond
 * `MAX_SLICES` the smallest fold into a neutral "other" slice.
 */
export function classBySymbol(accounts: readonly Account[], name: string): Allocation {
  const totals = new Map<string, string>();
  for (const account of accounts) {
    for (const position of account.positions) {
      if ((position.asset_class ?? UNCLASSIFIED) === name) {
        totals.set(
          position.symbol,
          addDecimal(totals.get(position.symbol) ?? "0", position.market_value),
        );
      }
    }
  }
  const { slices, excluded } = partition(
    totals,
    (key, amount, value) => ({ key, label: key, amount, value, slot: null, drillable: false }),
    (key) => key,
  );
  // Colored by rank: within one class the symbols are the entities, and the
  // largest ones are the ones worth telling apart.
  const kept = slices.length > MAX_SLICES ? slices.slice(0, MAX_SLICES - 1) : slices;
  const folded = slices.slice(kept.length);
  const result: Slice[] = kept.map((slice, index) => ({ ...slice, slot: index }));
  if (folded.length > 0) {
    const amount = folded.reduce((sum, slice) => addDecimal(sum, slice.amount), "0");
    result.push({
      key: OTHER,
      label: `${folded.length} others`,
      amount,
      value: Number(amount),
      slot: null,
      drillable: false,
    });
  }
  return { slices: result, excluded };
}
