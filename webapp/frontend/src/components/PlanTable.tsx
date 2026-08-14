import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Paper from "@mui/material/Paper";
import { alpha } from "@mui/material/styles";
import type { SxProps, Theme } from "@mui/material/styles";
import type { Action, Recommendation } from "../api";
import { money, moneyAbs } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import type { ReactElement } from "react";

/** An ignored class carries no action; the CLI leaves it blank too. */
function actionLabel(action: Action): string {
  return action === "" ? "IGNORED" : action;
}

const COLUMNS: readonly Column<Recommendation>[] = [
  { id: "action", label: "Action", value: (row) => actionLabel(row.action) },
  { id: "class", label: "Class", value: (row) => row.asset_class },
  {
    id: "amount",
    label: "Amount",
    numeric: true,
    // Sorted by size of the trade: a $9k buy and a $9k sell are equally large.
    value: (row) => Math.abs(Number(row.amount)),
  },
  {
    id: "current",
    label: "Current",
    numeric: true,
    value: (row) => Number(row.current_value),
  },
  {
    id: "target",
    label: "Target",
    numeric: true,
    value: (row) => Number(row.target_value),
  },
];

/** Palette entry a row is tinted with, or null for a row with no trade. */
function actionColor(action: Action): "success" | "error" | null {
  return action === "BUY" ? "success" : action === "SELL" ? "error" : null;
}

/**
 * Tints a row by its direction, buys green and sells red.
 *
 * Kept faint: it groups the plan at a glance, and the chip in the first cell
 * still carries the direction in words for anyone the color does not reach.
 */
function rowSx(action: Action): SxProps<Theme> | undefined {
  const color = actionColor(action);
  if (color === null) {
    return undefined;
  }
  return {
    backgroundColor: (theme: Theme) => alpha(theme.palette[color].main, 0.08),
    // Overrides MUI's own hover shade, which would otherwise wash out the tint.
    "&.MuiTableRow-hover:hover": {
      backgroundColor: (theme: Theme) => alpha(theme.palette[color].main, 0.16),
    },
  };
}

function ActionChip({ action }: { action: Action }): ReactElement {
  const color = actionColor(action);
  if (color === null) {
    // Ignored, unclassified, or HOLD: the rebalancer assumes no trade at all.
    return <Chip label={actionLabel(action)} size="small" variant="outlined" />;
  }
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
  // The rebalancer's own order is meaningful, so nothing is sorted until asked.
  const view = useTableView(recommendations, COLUMNS, "");
  return (
    <>
      <Box sx={{ display: "flex", justifyContent: "flex-end", mb: 1 }}>
        <CsvButton
          name={["plan", portfolio]}
          demo={demo}
          headers={COLUMNS.map((column) => column.label)}
          rows={view.rows.map((item) => [
            actionLabel(item.action),
            item.asset_class,
            item.amount,
            item.current_value,
            item.target_value,
          ])}
        />
      </Box>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <SortableHead columns={COLUMNS} view={view} />
          <TableBody>
            {view.rows.map((item) => (
              <TableRow key={item.asset_class} hover sx={rowSx(item.action)}>
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
