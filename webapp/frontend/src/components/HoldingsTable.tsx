import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { HoldingAccount } from "../api";
import { isNegative, money, shares } from "../format";
import type { ReactElement } from "react";

/** One account's equity positions, cash, and total — the CLI's holdings table. */
export default function HoldingsTable({
  account,
}: {
  account: HoldingAccount;
}): ReactElement {
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mb: 3 }}>
      <Typography variant="subtitle1" sx={{ fontWeight: 600, mb: 1 }}>
        {account.label}
      </Typography>
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
