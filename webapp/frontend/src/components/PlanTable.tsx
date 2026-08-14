import Box from "@mui/material/Box";
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
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

const CSV_HEADERS = ["Action", "Class", "Amount", "Current", "Target"] as const;

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
  portfolio,
  demo,
}: {
  recommendations: Recommendation[];
  /** Portfolio name, used to name the download. */
  portfolio: string;
  demo: boolean;
}): ReactElement {
  return (
    <>
      <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 1 }}>
        <CsvButton
          name={["plan", portfolio]}
          demo={demo}
          headers={CSV_HEADERS}
          rows={recommendations.map((item) => [
            // An ignored class carries no action; the CLI leaves it blank too.
            item.action === "" ? "IGNORED" : item.action,
            item.asset_class,
            item.amount,
            item.current_value,
            item.target_value,
          ])}
        />
      </Box>
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
    </>
  );
}
