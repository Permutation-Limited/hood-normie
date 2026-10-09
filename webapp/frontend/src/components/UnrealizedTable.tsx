import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import type { UnrealizedHolding, UnrealizedTotals } from "../api";
import type { CsvRow } from "../csv";
import { money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

function numberOrNull(value: string | null): number | null {
  return value === null ? null : Number(value);
}

const COLUMNS: readonly Column<UnrealizedHolding>[] = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  {
    id: "quantity",
    label: "Quantity",
    numeric: true,
    value: (row) => Number(row.quantity),
  },
  { id: "price", label: "Price", numeric: true, value: (row) => numberOrNull(row.price) },
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
  {
    id: "return",
    label: "Return",
    numeric: true,
    value: (row) => numberOrNull(row.return_rate),
  },
];

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

function rate(value: string | null): string {
  return value === null ? "—" : percent.format(Number(value));
}

function amount(value: string | null): string {
  return value === null ? "—" : money(value);
}

function gainColor(value: string | null): string | undefined {
  if (value === null || Number(value) === 0) {
    return undefined;
  }
  return Number(value) > 0 ? "success.main" : "error.main";
}

/** The rows as displayed plus the total, in exact decimal strings. */
function csvRows(rows: readonly UnrealizedHolding[], totals: UnrealizedTotals): CsvRow[] {
  return [
    ...rows.map((row) => [
      row.symbol,
      row.quantity,
      row.price,
      row.market_value,
      row.cost_basis,
      row.unrealized,
      row.return_rate,
    ]),
    [
      "TOTAL",
      null,
      null,
      totals.market_value,
      totals.cost_basis,
      totals.unrealized,
      totals.return_rate,
    ],
  ];
}

/** Holdings marked at the latest quote against their tax-lot cost basis. */
export default function UnrealizedTable({
  holdings,
  totals,
  name,
  demo,
}: {
  holdings: UnrealizedHolding[];
  totals: UnrealizedTotals;
  /** Used to name the download. */
  name: string;
  demo: boolean;
}): ReactElement {
  const view = useTableView(holdings, COLUMNS, "symbol");
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
        <Typography variant="subtitle2">Holdings</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <TableSearch value={view.query} onChange={view.setQuery} label="symbols" />
        <CsvButton
          name={["unrealized", name]}
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
                      ? "No equity positions"
                      : `No holding matches “${view.query}”`}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((row) => (
              <TableRow key={row.symbol} hover>
                <TableCell sx={{ fontWeight: 500 }}>{row.symbol}</TableCell>
                <TableCell align="right" sx={numeric}>
                  {shares(row.quantity)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {amount(row.price)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {amount(row.market_value)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {row.basis_source === "average cost" ? (
                    <Tooltip title="A tax lot's basis is still pending, so this is Robinhood's average cost">
                      <span>{amount(row.cost_basis)}*</span>
                    </Tooltip>
                  ) : (
                    amount(row.cost_basis)
                  )}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, color: gainColor(row.unrealized) }}
                >
                  {amount(row.unrealized)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, color: gainColor(row.unrealized) }}
                >
                  {rate(row.return_rate)}
                </TableCell>
              </TableRow>
            ))}
            {holdings.length > 0 && (
              <TableRow>
                {/* The whole set's total, unaffected by a filter above it. */}
                <TableCell colSpan={3} sx={{ fontWeight: 600 }}>
                  Total
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.market_value)}
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.cost_basis)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, fontWeight: 600, color: gainColor(totals.unrealized) }}
                >
                  {money(totals.unrealized)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, fontWeight: 600, color: gainColor(totals.unrealized) }}
                >
                  {rate(totals.return_rate)}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {totals.incomplete > 0 && (
        <Typography variant="caption" color="warning.main">
          {totals.incomplete} holding(s) without a price or cost basis are left
          out of the total.
        </Typography>
      )}
    </Box>
  );
}
