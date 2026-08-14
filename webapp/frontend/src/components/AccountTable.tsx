import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { Account, Position } from "../api";
import type { CsvRow } from "../csv";
import { isNegative, money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

const COLUMNS: readonly Column<Position>[] = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  { id: "class", label: "Class", value: (row) => row.asset_class },
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
function csvRows(positions: readonly Position[], account: Account): CsvRow[] {
  return [
    ...positions.map((position) => [
      position.symbol,
      position.asset_class,
      position.quantity,
      position.price,
      position.market_value,
    ]),
    ["CASH", null, null, null, account.cash],
    ["TOTAL", null, null, null, account.total_value],
  ];
}

export default function AccountTable({
  account,
  demo,
}: {
  account: Account;
  demo: boolean;
}): ReactElement {
  const view = useTableView(account.positions, COLUMNS, "symbol");
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction="row"
        spacing={1}
        alignItems="center"
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {account.label}
        </Typography>
        <Chip
          size="small"
          variant="outlined"
          label={account.kind === "robinhood" ? "Robinhood" : "External"}
        />
        <Box sx={{ flexGrow: 1 }} />
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
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <SortableHead columns={COLUMNS} view={view} />
          <TableBody>
            {view.rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={COLUMNS.length}>
                  <Typography variant="body2" color="text.secondary">
                    {view.total === 0 ? (
                      <>
                        No positions
                        {account.kind === "robinhood" &&
                          " — Robinhood returned no equity positions for this account. Verify its number in config.yaml."}
                      </>
                    ) : (
                      `No position matches “${view.query}”`
                    )}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((position) => (
              <TableRow key={position.symbol} hover>
                <TableCell sx={{ fontWeight: 500 }}>{position.symbol}</TableCell>
                <TableCell>
                  {position.asset_class ?? (
                    <Typography variant="body2" color="warning.main">
                      unclassified
                    </Typography>
                  )}
                </TableCell>
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
              <TableCell colSpan={4}>Cash</TableCell>
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
              <TableCell colSpan={4} sx={{ fontWeight: 600 }}>
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
