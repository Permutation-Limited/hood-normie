import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { WashSale } from "../api";
import { money, shares } from "../format";
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

/** How a sale's replacement purchases read: "03-05 5.98, 04-07 8.74 in IRA". */
function describe(item: WashSale): string {
  return item.replacements
    .map((buy) => {
      const where =
        buy.account_label === item.account_label ? "" : ` in ${buy.account_label}`;
      const ira = buy.tax_advantaged ? " (permanent)" : "";
      return `${buy.date.slice(5)}: ${shares(buy.quantity)} sh${where}${ira}`;
    })
    .join(", ");
}

/**
 * Loss sales that a nearby purchase may make wash sales. Flags only: the
 * numbers above are not adjusted, since Robinhood's gain may already be.
 */
export default function WashSales({
  washSales,
  total,
  demo,
}: {
  washSales: WashSale[];
  total: string;
  demo: boolean;
}): ReactElement | null {
  if (washSales.length === 0) {
    return null;
  }
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Alert severity="warning" sx={{ mb: 3, "& .MuiAlert-message": { width: "100%" } }}>
      <AlertTitle>
        Possible wash sales: up to {money(total)} of losses may be disallowed
      </AlertTitle>
      <Typography variant="body2" sx={{ mb: 1 }}>
        Shares of the same symbol were bought within 30 days of these losses,
        reinvested dividends included. A replacement in a retirement account
        makes the disallowed loss permanent; otherwise it moves into the new
        shares&apos; basis. Robinhood&apos;s gain may already reflect this, so the
        totals above are unadjusted; check your 1099-B.
      </Typography>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>Date</TableCell>
              <TableCell>Symbol</TableCell>
              <TableCell align="right">Loss</TableCell>
              <TableCell align="right">Replaced</TableCell>
              <TableCell align="right">Disallowed</TableCell>
              <TableCell>Replacement buys</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {washSales.map((item, index) => (
              <TableRow key={`${item.date}-${item.symbol}-${String(index)}`}>
                <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                  {item.date}
                </TableCell>
                <TableCell sx={{ fontWeight: 500 }}>{item.symbol}</TableCell>
                <TableCell align="right" sx={{ ...numeric, color: "error.main" }}>
                  {money(item.loss)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {shares(item.replaced)} of {shares(item.quantity)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {money(item.disallowed)}
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {describe(item)}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      <CsvButton
        name={["wash-sales"]}
        demo={demo}
        headers={["Date", "Symbol", "Account", "Quantity", "Loss", "Replaced",
          "Disallowed", "Permanent", "Replacement buys"]}
        rows={washSales.map((item) => [
          item.date,
          item.symbol,
          item.account_label,
          item.quantity,
          item.loss,
          item.replaced,
          item.disallowed,
          item.permanent,
          describe(item),
        ])}
      />
    </Alert>
  );
}
