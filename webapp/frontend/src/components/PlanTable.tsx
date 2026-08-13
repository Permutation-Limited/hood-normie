import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import type { Action, Recommendation } from "../api";
import { money, moneyAbs } from "../format";
import type { ReactElement } from "react";

function ActionChip({ action }: { action: Action }): ReactElement {
  if (action === "") {
    // Ignored or unclassified: the rebalancer assumes no trade at all.
    return <Chip label="IGNORED" size="small" variant="outlined" />;
  }
  const color = action === "BUY" ? "success" : action === "SELL" ? "error" : "default";
  return <Chip label={action} size="small" color={color} />;
}

export default function PlanTable({
  recommendations,
}: {
  recommendations: Recommendation[];
}): ReactElement {
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Action</TableCell>
            <TableCell>Class</TableCell>
            <TableCell align="right">Amount</TableCell>
            <TableCell align="right">Current</TableCell>
            <TableCell align="right">Target</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {recommendations.map((item) => (
            <TableRow key={item.asset_class} hover>
              <TableCell>
                <ActionChip action={item.action} />
              </TableCell>
              <TableCell sx={{ fontWeight: item.ignored ? 400 : 500 }}>
                {item.asset_class}
              </TableCell>
              <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                {moneyAbs(item.amount)}
              </TableCell>
              <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                {money(item.current_value)}
              </TableCell>
              <TableCell align="right" sx={{ fontVariantNumeric: "tabular-nums" }}>
                {money(item.target_value)}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
