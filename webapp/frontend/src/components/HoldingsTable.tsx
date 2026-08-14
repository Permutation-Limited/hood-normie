import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { HoldingAccount } from "../api";
import type { CsvRow } from "../csv";
import { isNegative, money, shares } from "../format";
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

const CSV_HEADERS = ["Symbol", "Quantity", "Price", "Value"] as const;

/** The rows as displayed, cash and total included, in exact decimal strings. */
function csvRows(account: HoldingAccount): CsvRow[] {
  return [
    ...account.positions.map((position) => [
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
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {account.label}
        </Typography>
        <CsvButton
          name={["holdings", account.label]}
          demo={demo}
          headers={CSV_HEADERS}
          rows={csvRows(account)}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {account.positions.length === 0 && (
              <TableRow>
                <TableCell colSpan={4}>
                  <Typography variant="body2" color="text.secondary">
                    No equity positions
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {account.positions.map((position) => (
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
