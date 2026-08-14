import { useMemo, useState } from "react";
import type { Column, Order } from "./sorting";
import { filterRows, sortRows } from "./sorting";

export interface TableView<T> {
  /** The rows to render: filtered by the query, then ordered. */
  rows: T[];
  /** How many rows exist before filtering, for an "n of m" hint. */
  total: number;
  order: Order;
  orderBy: string;
  toggleSort: (columnId: string) => void;
  query: string;
  setQuery: (query: string) => void;
}

/**
 * Search and sort state for one table.
 *
 * State is per-table and deliberately not in the URL: unlike demo mode, a
 * column order changes nothing about which numbers are shown, so it is not
 * worth the query-string noise.
 */
export function useTableView<T>(
  rows: readonly T[],
  columns: readonly Column<T>[],
  initialSort: string,
): TableView<T> {
  const [orderBy, setOrderBy] = useState(initialSort);
  const [order, setOrder] = useState<Order>("asc");
  const [query, setQuery] = useState("");

  const visible = useMemo(() => {
    const column = columns.find((item) => item.id === orderBy);
    return sortRows(filterRows(rows, columns, query), column, order);
  }, [rows, columns, query, orderBy, order]);

  return {
    rows: visible,
    total: rows.length,
    order,
    orderBy,
    toggleSort: (columnId: string) => {
      // Re-clicking the sorted column reverses it; a new column starts
      // ascending, which reads as A→Z and smallest-first.
      setOrder(columnId === orderBy && order === "asc" ? "desc" : "asc");
      setOrderBy(columnId);
    },
    query,
    setQuery,
  };
}
