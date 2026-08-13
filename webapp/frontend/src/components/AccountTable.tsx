import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { Account } from "../api";
import { isNegative, money, shares } from "../format";
import type { ReactElement } from "react";

export default function AccountTable({
  account,
}: {
  account: Account;
}): ReactElement {
  return (
    <Box sx={{ mb: 3 }}>
      <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }}>
        <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
          {account.label}
        </Typography>
        <Chip
          size="small"
          variant="outlined"
          label={account.kind === "robinhood" ? "Robinhood" : "External"}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Symbol</TableCell>
              <TableCell>Class</TableCell>
              <TableCell align="right">Quantity</TableCell>
              <TableCell align="right">Price</TableCell>
              <TableCell align="right">Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {account.positions.length === 0 && (
              <TableRow>
                <TableCell colSpan={5}>
                  <Typography variant="body2" color="text.secondary">
                    No positions
                    {account.kind === "robinhood" &&
                      " — Robinhood returned no equity positions for this account. Verify its number in config.yaml."}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {account.positions.map((position) => (
              <TableRow key={position.symbol} hover>
                <TableCell sx={{ fontWeight: 500 }}>{position.symbol}</TableCell>
                <TableCell>
                  {position.asset_class ?? (
                    <Typography variant="body2" color="warning.main">
                      unclassified
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                  {shares(position.quantity)}
                </TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                  {money(position.price)}
                </TableCell>
                <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                  {money(position.market_value)}
                </TableCell>
              </TableRow>
            ))}
            <TableRow>
              <TableCell colSpan={4}>Cash</TableCell>
              <TableCell
                align="right"
                sx={{
                  fontVariantNumeric: "tabular-nums",
                  color: isNegative(account.cash) ? "error.main" : undefined,
                }}
              >
                {money(account.cash)}
              </TableCell>
            </TableRow>
            <TableRow>
              <TableCell colSpan={4} sx={{ fontWeight: 600 }}>
                Total
              </TableCell>
              <TableCell
                align="right"
                sx={{ fontWeight: 600, fontVariantNumeric: "tabular-nums" }}
              >
                {money(account.total_value)}
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
