import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { DividendSummary, IncomeTotals } from "../api";
import type { CsvRow } from "../csv";
import { money } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

const COLUMNS: readonly Column<DividendSummary>[] = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  { id: "payments", label: "Payments", numeric: true, value: (row) => row.payments },
  { id: "paid", label: "Paid", numeric: true, value: (row) => Number(row.paid) },
  {
    id: "qualified",
    label: "Qualified",
    numeric: true,
    value: (row) => Number(row.qualified),
  },
  {
    id: "nonqualified",
    label: "Non-qualified",
    numeric: true,
    value: (row) => Number(row.nonqualified),
  },
  {
    id: "unclassified",
    label: "Unclassified",
    numeric: true,
    value: (row) => Number(row.unclassified),
  },
];

/** The rows as displayed plus the account's total, in exact decimal strings. */
function csvRows(rows: readonly DividendSummary[], totals: IncomeTotals): CsvRow[] {
  return [
    ...rows.map((row) => [
      row.symbol,
      String(row.payments),
      row.paid,
      row.qualified,
      row.nonqualified,
      row.unclassified,
    ]),
    [
      "TOTAL",
      null,
      totals.dividends,
      totals.qualified,
      totals.nonqualified,
      totals.unclassified,
    ],
  ];
}

/** One account's reinvested dividends by symbol, split by qualification. */
export default function DividendsTable({
  dividends,
  totals,
  account,
  demo,
}: {
  dividends: DividendSummary[];
  totals: IncomeTotals;
  /** Account label, used to name the download. */
  account: string;
  demo: boolean;
}): ReactElement {
  const view = useTableView(dividends, COLUMNS, "symbol");
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle2">Reinvested dividends</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <TableSearch value={view.query} onChange={view.setQuery} label="symbols" />
        <CsvButton
          name={["dividends", account]}
          demo={demo}
          headers={COLUMNS.map((column) => column.label)}
          rows={csvRows(view.rows, totals)}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <SortableHead columns={COLUMNS} view={view} />
          <TableBody>
            {view.rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length}>
                  <Typography variant="body2" color="text.secondary">
                    {view.total === 0
                      ? "No reinvested dividends this year"
                      : `No symbol matches “${view.query}”`}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((row) => (
              <TableRow key={row.symbol} hover>
                <TableCell sx={{ fontWeight: 500 }}>{row.symbol}</TableCell>
                <TableCell align="right" sx={numeric}>
                  {row.payments}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(row.paid)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(row.qualified)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(row.nonqualified)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    ...numeric,
                    color: Number(row.unclassified) !== 0 ? "warning.main" : undefined,
                  }}
                >
                  {money(row.unclassified)}
                </TableCell>
              </TableRow>
            ))}
            {dividends.length > 0 && (
              <TableRow>
                {/* The account's own total, unaffected by a filter above it. */}
                <TableCell colSpan={2} sx={{ fontWeight: 600 }}>
                  Total
                </TableCell>
                {[
                  totals.dividends,
                  totals.qualified,
                  totals.nonqualified,
                  totals.unclassified,
                ].map((value, index) => (
                  <TableCell
                    key={index}
                    align="right"
                    sx={{ ...numeric, fontWeight: 600 }}
                  >
                    {money(value)}
                  </TableCell>
                ))}
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
