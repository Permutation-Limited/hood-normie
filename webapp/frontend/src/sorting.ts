/**
 * Sorting and filtering for the data tables.
 *
 * Money and quantities are parsed to `number` here, which is safe because the
 * result only ever decides an order — the values a row displays, totals, and
 * exports all keep the API's exact decimal strings.
 */

export type Order = "asc" | "desc";

export interface Column<T> {
  readonly id: string;
  readonly label: string;
  /** Right-aligned in the head, and compared numerically. */
  readonly numeric?: boolean;
  /** The value this column sorts and searches on; null when unavailable. */
  readonly value: (row: T) => string | number | null;
}

/**
 * Order rows by one column.
 *
 * Unavailable values sort last ascending (and so first descending), keeping
 * them out of the way of the data a reader is scanning for.
 */
export function sortRows<T>(
  rows: readonly T[],
  column: Column<T> | undefined,
  order: Order,
): T[] {
  if (!column) {
    return [...rows];
  }
  const sign = order === "asc" ? 1 : -1;
  return [...rows].sort(
    (left, right) => sign * compare(column.value(left), column.value(right)),
  );
}

export function compare(
  left: string | number | null,
  right: string | number | null,
): number {
  if (left === null || right === null) {
    return left === right ? 0 : left === null ? 1 : -1;
  }
  if (typeof left === "number" && typeof right === "number") {
    return left - right;
  }
  return String(left).localeCompare(String(right), undefined, {
    sensitivity: "base",
    numeric: true,
  });
}

/** Keep rows where any column contains the query, case-insensitively. */
export function filterRows<T>(
  rows: readonly T[],
  columns: readonly Column<T>[],
  query: string,
): T[] {
  const needle = query.trim().toLowerCase();
  if (!needle) {
    return [...rows];
  }
  return rows.filter((row) =>
    columns.some((column) =>
      String(column.value(row) ?? "")
        .toLowerCase()
        .includes(needle),
    ),
  );
}
