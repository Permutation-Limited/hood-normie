import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { Holding, HoldingAccount } from "../api";
import type { CsvRow } from "../csv";
import { isNegative, money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

const COLUMNS: readonly Column<Holding>[] = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  {
    id: "quantity",
    label: "Quantity",
    numeric: true,
    value: (row) => Number(row.quantity),
  },
  { id: "price", label: "Price", numeric: true, value: (row) => Number(row.price) },
  {
    id: "value",
    label: "Value",
    numeric: true,
    value: (row) => Number(row.market_value),
  },
];

/** The rows as displayed, cash and total included, in exact decimal strings. */
function csvRows(positions: readonly Holding[], account: HoldingAccount): CsvRow[] {
  return [
    ...positions.map((position) => [
      position.symbol,
      position.quantity,
      position.price,
      position.market_value,
    ]),
    ["CASH", null, null, account.cash],
    ["TOTAL", null, null, account.total_value],
  ];
}

/** One account's equity positions, cash, and total — the CLI's holdings table. */
export default function HoldingsTable({
  account,
  demo,
}: {
  account: HoldingAccount;
  demo: boolean;
}): ReactElement {
  const view = useTableView(account.positions, COLUMNS, "symbol");
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        spacing={1}
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {account.label}
        </Typography>
        <Stack direction="row" alignItems="center" spacing={1}>
          <TableSearch
            value={view.query}
            onChange={view.setQuery}
            label="symbols"
          />
          {/* Exports what is on screen, filtering included. */}
          <CsvButton
            name={["holdings", account.label]}
            demo={demo}
            headers={COLUMNS.map((column) => column.label)}
            rows={csvRows(view.rows, account)}
          />
        </Stack>
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
                      : `No position matches “${view.query}”`}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((position) => (
              <TableRow key={position.symbol} hover>
                <TableCell sx={{ fontWeight: 500 }}>{position.symbol}</TableCell>
                <TableCell align="right" sx={numeric}>
                  {shares(position.quantity)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(position.price)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(position.market_value)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell colSpan={3}>Cash</TableCell>
              <TableCell
                align="right"
                sx={{
                  ...numeric,
                  color: isNegative(account.cash) ? "error.main" : undefined,
                }}
              >
                {money(account.cash)}
              </TableCell>
            </TableRow>
            <TableRow>
              {/* The account's own total, unaffected by a filter above it. */}
              <TableCell colSpan={3} sx={{ fontWeight: 600 }}>
                Total
              </TableCell>
              <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                {money(account.total_value)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
