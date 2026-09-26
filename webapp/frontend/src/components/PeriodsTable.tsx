import Box from "@mui/material/Box";
import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import type { IncomeTotals, TaxablePeriod, TaxPeriod, TreatmentRange } from "../api";
import { money } from "../format";
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

type View = "period" | "cumulative";
type Grouping = "rate" | "detail";

interface Column<P> {
  label: string;
  value: (period: P, view: View) => string;
  /** Still needs classifying before it can go into an estimate. */
  unresolved?: boolean;
}

function totals(period: TaxPeriod, view: View): IncomeTotals {
  return view === "period" ? period.totals : period.cumulative;
}

function treatment(period: TaxablePeriod, view: View): TreatmentRange {
  return view === "period" ? period.treatment : period.cumulative_treatment;
}

const DETAIL: readonly Column<TaxPeriod>[] = [
  { label: "Short-term", value: (p, v) => totals(p, v).short_term },
  { label: "Long-term", value: (p, v) => totals(p, v).long_term },
  {
    label: "Unknown term",
    value: (p, v) => totals(p, v).unknown_term,
    unresolved: true,
  },
  { label: "Qualified", value: (p, v) => totals(p, v).qualified },
  { label: "Non-qualified", value: (p, v) => totals(p, v).nonqualified },
  {
    label: "Unclassified",
    value: (p, v) => totals(p, v).unclassified,
    unresolved: true,
  },
];

const BY_RATE: readonly Column<TaxablePeriod>[] = [
  { label: "Ordinary", value: (p, v) => treatment(p, v).known.ordinary },
  { label: "Preferential", value: (p, v) => treatment(p, v).known.preferential },
  {
    label: "Unresolved",
    value: (p, v) => {
      const range = treatment(p, v);
      return String(
        Number(range.unresolved_gains) + Number(range.unresolved_dividends),
      );
    },
    unresolved: true,
  },
];

function isTaxable(periods: readonly TaxPeriod[]): periods is TaxablePeriod[] {
  return periods.every((period) => "treatment" in period);
}

/**
 * Income by IRS estimated-tax period.
 *
 * Rows stay in period order and are not sortable: the order is the point. The
 * year-to-date view is what Form 2210's annualized method (Schedule AI) asks
 * for — income through Mar 31, May 31, Aug 31, and Dec 31. The taxable total
 * can also be grouped by tax rate; each period's share there is the change in
 * the year-to-date figure, since losses only net over a running total.
 */
export default function PeriodsTable({
  periods,
  account,
  demo,
}: {
  periods: TaxPeriod[] | TaxablePeriod[];
  /** Used to name the download. */
  account: string;
  demo: boolean;
}): ReactElement {
  const [view, setView] = useState<View>("period");
  const [grouping, setGrouping] = useState<Grouping>("rate");
  const taxable = isTaxable(periods);
  const byRate = taxable && grouping === "rate";
  // Widened for rendering; the rate columns only ever see taxable periods.
  const columns = (byRate ? BY_RATE : DETAIL) as readonly Column<TaxPeriod>[];
  const numeric = { fontVariantNumeric: "tabular-nums" } as const;
  return (
    <Box sx={{ mt: 2 }}>
      <Stack
        direction="row"
        alignItems="center"
        spacing={1}
        flexWrap="wrap"
        useFlexGap
        sx={{ mb: 1 }}
      >
        <Typography variant="subtitle2">By estimated-tax period</Typography>
        <Box sx={{ flexGrow: 1 }} />
        {taxable && (
          <ToggleButtonGroup
            exclusive
            size="small"
            value={grouping}
            onChange={(_, value: Grouping | null) => {
              if (value !== null) {
                setGrouping(value);
              }
            }}
            aria-label="Grouping"
          >
            <ToggleButton value="rate">By tax rate</ToggleButton>
            <ToggleButton value="detail">Detail</ToggleButton>
          </ToggleButtonGroup>
        )}
        <ToggleButtonGroup
          exclusive
          size="small"
          value={view}
          onChange={(_, value: View | null) => {
            if (value !== null) {
              setView(value);
            }
          }}
          aria-label="Period totals"
        >
          <ToggleButton value="period">Each period</ToggleButton>
          <ToggleButton value="cumulative">Year to date</ToggleButton>
        </ToggleButtonGroup>
        <CsvButton
          name={["periods", byRate ? "by-rate" : "detail", view, account]}
          demo={demo}
          headers={["Period", "Start", "End", "Due", ...columns.map((c) => c.label)]}
          rows={periods.map((period: TaxPeriod) => [
            period.label,
            period.start,
            period.end,
            period.due,
            ...columns.map((column) => column.value(period, view)),
          ])}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{view === "period" ? "Period" : "Through"}</TableCell>
              <TableCell>Due</TableCell>
              {columns.map((column) => (
                <TableCell
                  key={column.label}
                  align="right"
                  sx={{ whiteSpace: "nowrap" }}
                >
                  {column.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {periods.map((period: TaxPeriod) => (
              <TableRow key={period.number} hover>
                <TableCell sx={{ whiteSpace: "nowrap", fontWeight: 500 }}>
                  {view === "period" ? period.label : period.label.split("–")[1]}
                </TableCell>
                <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                  {period.due}
                </TableCell>
                {columns.map((column) => {
                  const value = column.value(period, view);
                  const attention = column.unresolved === true && Number(value) !== 0;
                  return (
                    <TableCell
                      key={column.label}
                      align="right"
                      sx={{
                        ...numeric,
                        color: attention
                          ? "warning.main"
                          : Number(value) < 0
                            ? "error.main"
                            : undefined,
                      }}
                    >
                      {money(value)}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      {byRate && (
        <Typography variant="caption" color="text.secondary">
          A negative ordinary amount is net capital loss deducted against
          ordinary income. Unresolved amounts are left out of both columns.
        </Typography>
      )}
    </Box>
  );
}
