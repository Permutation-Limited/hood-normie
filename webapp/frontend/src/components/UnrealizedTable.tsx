import Box from "@mui/material/Box";
import Collapse from "@mui/material/Collapse";
import IconButton from "@mui/material/IconButton";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import KeyboardArrowDownIcon from "@mui/icons-material/KeyboardArrowDown";
import KeyboardArrowRightIcon from "@mui/icons-material/KeyboardArrowRight";
import { Fragment, useState } from "react";
import type { UnrealizedHolding, UnrealizedTotals } from "../api";
import type { CsvRow } from "../csv";
import { money, shares } from "../format";
import type { Column } from "../sorting";
import { useTableView } from "../useTableView";
import CsvButton from "./CsvButton";
import LotsPanel from "./LotsPanel";
import SortableHead from "./SortableHead";
import TableSearch from "./TableSearch";
import type { ReactElement } from "react";

function numberOrNull(value: string | null): number | null {
  return value === null ? null : Number(value);
}

const COLUMNS: readonly Column<UnrealizedHolding>[] = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  {
    id: "quantity",
    label: "Quantity",
    numeric: true,
    value: (row) => Number(row.quantity),
  },
  { id: "price", label: "Price", numeric: true, value: (row) => numberOrNull(row.price) },
  {
    id: "value",
    label: "Value",
    numeric: true,
    value: (row) => numberOrNull(row.market_value),
  },
  {
    id: "basis",
    label: "Cost basis",
    numeric: true,
    value: (row) => numberOrNull(row.cost_basis),
  },
  {
    id: "gain",
    label: "Gain",
    numeric: true,
    value: (row) => numberOrNull(row.unrealized),
  },
  {
    id: "return",
    label: "Return",
    numeric: true,
    value: (row) => numberOrNull(row.return_rate),
  },
  {
    id: "short",
    label: "Short-term",
    numeric: true,
    value: (row) => (row.unrealized === null ? null : Number(row.short_term)),
  },
  {
    id: "long",
    label: "Long-term",
    numeric: true,
    value: (row) => (row.unrealized === null ? null : Number(row.long_term)),
  },
];

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

function rate(value: string | null): string {
  return value === null ? "—" : percent.format(Number(value));
}

function amount(value: string | null): string {
  return value === null ? "—" : money(value);
}

function gainColor(value: string | null): string | undefined {
  if (value === null || Number(value) === 0) {
    return undefined;
  }
  return Number(value) > 0 ? "success.main" : "error.main";
}

/** The rows as displayed plus the total, in exact decimal strings. */
function csvRows(rows: readonly UnrealizedHolding[], totals: UnrealizedTotals): CsvRow[] {
  return [
    ...rows.map((row) => [
      row.symbol,
      row.quantity,
      row.price,
      row.market_value,
      row.cost_basis,
      row.unrealized,
      row.return_rate,
      row.short_term,
      row.long_term,
    ]),
    [
      "TOTAL",
      null,
      null,
      totals.market_value,
      totals.cost_basis,
      totals.unrealized,
      totals.return_rate,
      totals.short_term,
      totals.long_term,
    ],
  ];
}

/** Holdings marked at the latest quote against their tax-lot cost basis. */
export default function UnrealizedTable({
  holdings,
  totals,
  name,
  demo,
  accountLabels,
}: {
  holdings: UnrealizedHolding[];
  totals: UnrealizedTotals;
  /** Used to name the download. */
  name: string;
  demo: boolean;
  /** Account number to label, for lots that span several accounts. */
  accountLabels: ReadonlyMap<string, string>;
}): ReactElement {
  const view = useTableView(holdings, COLUMNS, "symbol");
  // Expanded rows by symbol. A row's lots are fetched when it first opens.
  const [open, setOpen] = useState<ReadonlySet<string>>(new Set());
  const toggle = (symbol: string): void => {
    setOpen((current) => {
      const next = new Set(current);
      if (next.has(symbol)) {
        next.delete(symbol);
      } else {
        next.add(symbol);
      }
      return next;
    });
  };
  const span = COLUMNS.length + 1;
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle2">Holdings</Typography>
        <Box sx={{ flexGrow: 1 }} />
        <TableSearch value={view.query} onChange={view.setQuery} label="symbols" />
        <CsvButton
          name={["unrealized", name]}
          demo={demo}
          headers={COLUMNS.map((column) => column.label)}
          rows={csvRows(view.rows, totals)}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <SortableHead columns={COLUMNS} view={view} leading />
          <TableBody>
            {view.rows.length === 0 && (
              <TableRow>
                <TableCell colSpan={span}>
                  <Typography variant="body2" color="text.secondary">
                    {view.total === 0
                      ? "No equity positions"
                      : `No holding matches “${view.query}”`}
                  </Typography>
                </TableCell>
              </TableRow>
            )}
            {view.rows.map((row) => (
              <Fragment key={row.symbol}>
              <TableRow hover sx={{ "& > td": { borderBottom: open.has(row.symbol) ? "none" : undefined } }}>
                <TableCell padding="none" sx={{ width: 40, pl: 0.5 }}>
                  {row.lot_count > 0 && (
                    <IconButton
                      size="small"
                      aria-label={`${open.has(row.symbol) ? "Hide" : "Show"} ${row.symbol} tax lots`}
                      aria-expanded={open.has(row.symbol)}
                      onClick={() => {
                        toggle(row.symbol);
                      }}
                    >
                      {open.has(row.symbol) ? (
                        <KeyboardArrowDownIcon fontSize="small" />
                      ) : (
                        <KeyboardArrowRightIcon fontSize="small" />
                      )}
                    </IconButton>
                  )}
                </TableCell>
                <TableCell sx={{ fontWeight: 500, whiteSpace: "nowrap" }}>
                  {row.symbol}
                  {row.lot_count > 0 && (
                    <Typography variant="caption" color="text.secondary" sx={{ ml: 1 }}>
                      {row.lot_count} lot{row.lot_count === 1 ? "" : "s"}
                    </Typography>
                  )}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {shares(row.quantity)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {amount(row.price)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {amount(row.market_value)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {row.basis_source === "average cost" ? (
                    <Tooltip title="A tax lot's basis is still pending, so this is Robinhood's average cost">
                      <span>{amount(row.cost_basis)}*</span>
                    </Tooltip>
                  ) : (
                    amount(row.cost_basis)
                  )}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, color: gainColor(row.unrealized) }}
                >
                  {amount(row.unrealized)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, color: gainColor(row.unrealized) }}
                >
                  {rate(row.return_rate)}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {row.unrealized === null || row.basis_source !== "tax lots"
                    ? "—"
                    : money(row.short_term)}
                  {row.next_long_term && (
                    <Tooltip title="When the earliest short-term lot goes long-term">
                      <Typography
                        variant="caption"
                        color="text.secondary"
                        component="div"
                      >
                        LT {row.next_long_term}
                      </Typography>
                    </Tooltip>
                  )}
                </TableCell>
                <TableCell align="right" sx={numeric}>
                  {row.unrealized === null || row.basis_source !== "tax lots"
                    ? "—"
                    : money(row.long_term)}
                </TableCell>
              </TableRow>
              {open.has(row.symbol) && (
                <TableRow>
                  <TableCell colSpan={span} sx={{ py: 0, bgcolor: "action.hover" }}>
                    <Collapse in timeout="auto" unmountOnExit>
                      <LotsPanel
                        symbol={row.symbol}
                        accounts={row.account_numbers}
                        accountLabels={accountLabels}
                      />
                    </Collapse>
                  </TableCell>
                </TableRow>
              )}
              </Fragment>
            ))}
            {holdings.length > 0 && (
              <TableRow>
                {/* The whole set's total, unaffected by a filter above it. */}
                <TableCell colSpan={4} sx={{ fontWeight: 600 }}>
                  Total
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.market_value)}
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.cost_basis)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, fontWeight: 600, color: gainColor(totals.unrealized) }}
                >
                  {money(totals.unrealized)}
                </TableCell>
                <TableCell
                  align="right"
                  sx={{ ...numeric, fontWeight: 600, color: gainColor(totals.unrealized) }}
                >
                  {rate(totals.return_rate)}
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.short_term)}
                </TableCell>
                <TableCell align="right" sx={{ ...numeric, fontWeight: 600 }}>
                  {money(totals.long_term)}
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>
      {Number(totals.unknown_term) !== 0 && (
        <Typography variant="caption" color="warning.main" component="p">
          {money(totals.unknown_term)} of the gain is on holdings without a lot
          basis (marked *), so it is in neither term column.
        </Typography>
      )}
      {totals.incomplete > 0 && (
        <Typography variant="caption" color="warning.main">
          {totals.incomplete} holding(s) without a price or cost basis are left
          out of the total.
        </Typography>
      )}
    </Box>
  );
}
