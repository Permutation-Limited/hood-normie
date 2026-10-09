import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import type { Lot, LotTerm } from "../api";
import { fetchLots } from "../api";
import { money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import { useMemo } from "react";
import type { ReactElement } from "react";

const TERM_LABELS: Record<LotTerm, string> = {
  short: "Short",
  long: "Long",
  unknown: "Unknown",
};

function numberOrNull(value: string | null): number | null {
  return value === null ? null : Number(value);
}

/** Lot columns; the account column only when lots span several accounts. */
function lotColumns(
  accountLabels: ReadonlyMap<string, string>,
  several: boolean,
): readonly Column<Lot>[] {
  const account: Column<Lot> = {
    id: "account",
    label: "Account",
    value: (row) => accountLabels.get(row.account_number) ?? row.account_number,
  };
  return [
    ...(several ? [account] : []),
    // ISO dates sort correctly as text.
    { id: "acquired", label: "Acquired", value: (row) => row.acquired },
    { id: "term", label: "Term", value: (row) => TERM_LABELS[row.term] },
    {
      id: "quantity",
      label: "Quantity",
      numeric: true,
      value: (row) => Number(row.quantity),
    },
    {
      id: "value",
      label: "Value",
      numeric: true,
      value: (row) => numberOrNull(row.market_value),
    },
    {
      id: "basis",
      label: "Cost basis",
      numeric: true,
      value: (row) => numberOrNull(row.cost_basis),
    },
    {
      id: "gain",
      label: "Gain",
      numeric: true,
      value: (row) => numberOrNull(row.unrealized),
    },
    { id: "long_term_on", label: "Long-term on", value: (row) => row.long_term_on },
  ];
}

const NO_LOTS: readonly Lot[] = [];

function amount(value: string | null): string {
  return value === null ? "—" : money(value);
}

function gainColor(value: string | null): string | undefined {
  if (value === null || Number(value) === 0) {
    return undefined;
  }
  return Number(value) > 0 ? "success.main" : "error.main";
}

/**
 * One holding's open tax lots, loaded only once its row is expanded: a
 * holding can have dozens of lots, and most readers never open most rows.
 */
export default function LotsPanel({
  symbol,
  accounts,
  accountLabels,
}: {
  symbol: string;
  accounts: readonly string[];
  /** Account number to label, shown when lots span several accounts. */
  accountLabels: ReadonlyMap<string, string>;
}): ReactElement {
  const { demo } = useSearch({ strict: false });
  const isDemo = Boolean(demo);
  const { data, error, isFetching } = useQuery({
    queryKey: ["lots", symbol, accounts, isDemo],
    queryFn: ({ signal }) => fetchLots(symbol, accounts, { demo: isDemo, signal }),
    staleTime: 60_000,
    refetchOnWindowFocus: false,
    retry: false,
  });
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  const several = accounts.length > 1;
  const columns = useMemo(
    () => lotColumns(accountLabels, several),
    [accountLabels, several],
  );
  // Called before the early returns below: hooks must run on every render.
  const view = useTableView(data?.lots ?? NO_LOTS, columns, "acquired");

  if (error != null) {
    return (
      <Alert severity="error" sx={{ my: 1 }}>
        {error instanceof Error ? error.message : String(error)}
      </Alert>
    );
  }
  if (!data) {
    return (
      <Stack direction="row" spacing={1} alignItems="center" sx={{ py: 1 }}>
        <CircularProgress size={16} />
        <Typography variant="body2" color="text.secondary">
          {isFetching ? `Fetching ${symbol}'s tax lots…` : "No lots"}
        </Typography>
      </Stack>
    );
  }

  const rows = view.rows;
  return (
    <Box sx={{ py: 1 }}>
      <Stack direction="row" alignItems="center" sx={{ mb: 0.5 }}>
        <Typography variant="caption" color="text.secondary" sx={{ flexGrow: 1 }}>
          {rows.length} open lot{rows.length === 1 ? "" : "s"}, marked at{" "}
          {amount(data.price)}. Terms are Robinhood&apos;s, which count a wash
          sale&apos;s inherited holding period; &ldquo;long-term on&rdquo; dates
          count from the purchase date.
        </Typography>
        <CsvButton
          name={["lots", symbol]}
          demo={data.demo}
          headers={["Account", "Acquired", "Term", "Quantity", "Value", "Cost basis",
            "Gain", "Long-term on"]}
          rows={rows.map((lot: Lot) => [
            lot.account_number,
            lot.acquired,
            lot.term,
            lot.quantity,
            lot.market_value,
            lot.cost_basis,
            lot.unrealized,
            lot.long_term_on,
          ])}
        />
      </Stack>
      <Table size="small">
        <SortableHead columns={columns} view={view} />
        <TableBody>
          {rows.map((lot, index) => (
            <TableRow key={`${lot.account_number}-${lot.acquired ?? ""}-${String(index)}`}>
              {several && (
                <TableCell>
                  <Typography variant="body2" color="text.secondary" noWrap>
                    {accountLabels.get(lot.account_number) ?? lot.account_number}
                  </Typography>
                </TableCell>
              )}
              <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                {lot.acquired ?? "—"}
              </TableCell>
              <TableCell>
                <Chip
                  size="small"
                  variant="outlined"
                  label={TERM_LABELS[lot.term]}
                  color={lot.term === "unknown" ? "warning" : "default"}
                />
              </TableCell>
              <TableCell align="right" sx={numeric}>
                {shares(lot.quantity)}
              </TableCell>
              <TableCell align="right" sx={numeric}>
                {amount(lot.market_value)}
              </TableCell>
              <TableCell align="right" sx={numeric}>
                {amount(lot.cost_basis)}
              </TableCell>
              <TableCell align="right" sx={{ ...numeric, color: gainColor(lot.unrealized) }}>
                {amount(lot.unrealized)}
              </TableCell>
              <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                {lot.long_term_on ?? ""}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
