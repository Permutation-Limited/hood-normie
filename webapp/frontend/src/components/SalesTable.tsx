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
import type { Sale, Term } from "../api";
import { isNegative, money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

const TERM_LABELS: Record<Term, string> = {
  short: "Short",
  long: "Long",
  unknown: "Unknown",
};

const COLUMNS: readonly Column<Sale>[] = [
  { id: "date", label: "Date", value: (row) => row.date },
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  {
    id: "quantity",
    label: "Quantity",
    numeric: true,
    value: (row) => Number(row.quantity),
  },
  { id: "gain", label: "Gain", numeric: true, value: (row) => Number(row.gain) },
  { id: "term", label: "Term", value: (row) => TERM_LABELS[row.term] },
  { id: "basis", label: "Basis", value: (row) => row.reason },
];

function TermChip({
  term,
  taxAdvantaged,
}: {
  term: Term;
  taxAdvantaged: boolean;
}): ReactElement {
  if (taxAdvantaged) {
    // Not a gap to fill in: the holding period simply does not matter here.
    return <Chip label="n/a" size="small" variant="outlined" />;
  }
  if (term === "unknown") {
    return <Chip label="Unknown" size="small" color="warning" variant="outlined" />;
  }
  return <Chip label={TERM_LABELS[term]} size="small" variant="outlined" />;
}

/** One account's closing trades, each with its holding period and why. */
export default function SalesTable({
  sales,
  account,
  taxAdvantaged,
  demo,
}: {
  sales: Sale[];
  taxAdvantaged: boolean;
  /** Account label, used to name the download. */
  account: string;
  demo: boolean;
}): ReactElement {
  const view = useTableView(sales, COLUMNS, "date");
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mb: 3 }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle2">Realized gains</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <TableSearch value={view.query} onChange={view.setQuery} label="sales" />
        <CsvButton
          name={["realized", account]}
          demo={demo}
          headers={COLUMNS.map((column) => column.label)}
          rows={view.rows.map((sale) => [
            sale.date,
            sale.symbol,
            sale.quantity,
            sale.gain,
            sale.term,
            sale.reason,
          ])}
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
                      ? "No closing trades this year"
                      : `No sale matches “${view.query}”`}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((sale, index) => (
              // A single order can close several trades with identical fields.
              <TableRow key={`${sale.date}-${sale.symbol}-${String(index)}`} hover>
                <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                  {sale.date}
                </TableCell>
                <TableCell sx={{ fontWeight: 500 }}>{sale.symbol}</TableCell>
                <TableCell align="right" sx={numeric}>
                  {shares(sale.quantity)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{
                    ...numeric,
                    color: isNegative(sale.gain) ? "error.main" : undefined,
                  }}
                >
                  {money(sale.gain)}
                </TableCell>
                <TableCell>
                  <TermChip term={sale.term} taxAdvantaged={taxAdvantaged} />
                </TableCell>
                <TableCell>
                  <Typography variant="body2" color="text.secondary">
                    {sale.reason}
                  </Typography>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
    </Box>
  );
}
