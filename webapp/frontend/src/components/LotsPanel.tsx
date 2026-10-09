import Alert from "@mui/material/Alert";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { useQuery } from "@tanstack/react-query";
import { useSearch } from "@tanstack/react-router";
import type { Lot, LotTerm } from "../api";
import { fetchLots } from "../api";
import { money, shares } from "../format";
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

const TERM_LABELS: Record<LotTerm, string> = {
  short: "Short",
  long: "Long",
  unknown: "Unknown",
};

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

  const rows = data.lots;
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
        <TableHead>
          <TableRow>
            {several && <TableCell>Account</TableCell>}
            <TableCell>Acquired</TableCell>
            <TableCell>Term</TableCell>
            <TableCell align="right">Quantity</TableCell>
            <TableCell align="right">Value</TableCell>
            <TableCell align="right">Cost basis</TableCell>
            <TableCell align="right">Gain</TableCell>
            <TableCell>Long-term on</TableCell>
          </TableRow>
        </TableHead>
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
