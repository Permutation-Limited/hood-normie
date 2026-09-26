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
import type { IncomeTotals, TaxPeriod } from "../api";
import { money } from "../format";
import CsvButton from "./CsvButton";
import type { ReactElement } from "react";

type View = "period" | "cumulative";

interface Bucket {
  label: string;
  value: (totals: IncomeTotals) => string;
  /** Still needs classifying before it can go into an estimate. */
  unresolved?: boolean;
}

const BUCKETS: readonly Bucket[] = [
  { label: "Short-term", value: (t) => t.short_term },
  { label: "Long-term", value: (t) => t.long_term },
  { label: "Unknown term", value: (t) => t.unknown_term, unresolved: true },
  { label: "Qualified", value: (t) => t.qualified },
  { label: "Non-qualified", value: (t) => t.nonqualified },
  { label: "Unclassified", value: (t) => t.unclassified, unresolved: true },
];

/**
 * Income by IRS estimated-tax period.
 *
 * Rows stay in period order and are not sortable: the order is the point. The
 * year-to-date view is what Form 2210's annualized method (Schedule AI) asks
 * for — income through Mar 31, May 31, Aug 31, and Dec 31.
 */
export default function PeriodsTable({
  periods,
  account,
  demo,
}: {
  periods: TaxPeriod[];
  /** Used to name the download. */
  account: string;
  demo: boolean;
}): ReactElement {
  const [view, setView] = useState<View>("period");
  const pick = (period: TaxPeriod): IncomeTotals =>
    view === "period" ? period.totals : period.cumulative;
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
          name={["periods", view, account]}
          demo={demo}
          headers={["Period", "Start", "End", "Due", ...BUCKETS.map((b) => b.label)]}
          rows={periods.map((period) => [
            period.label,
            period.start,
            period.end,
            period.due,
            ...BUCKETS.map((bucket) => bucket.value(pick(period))),
          ])}
        />
      </Stack>
      <TableContainer component={Paper} variant="outlined">
        <Table size="small">
          <TableHead>
            <TableRow>
              <TableCell>{view === "period" ? "Period" : "Through"}</TableCell>
              <TableCell>Due</TableCell>
              {BUCKETS.map((bucket) => (
                <TableCell
                  key={bucket.label}
                  align="right"
                  sx={{ whiteSpace: "nowrap" }}
                >
                  {bucket.label}
                </TableCell>
              ))}
            </TableRow>
          </TableHead>
          <TableBody>
            {periods.map((period) => (
              <TableRow key={period.number} hover>
                <TableCell sx={{ whiteSpace: "nowrap", fontWeight: 500 }}>
                  {view === "period" ? period.label : period.label.split("–")[1]}
                </TableCell>
                <TableCell sx={{ ...numeric, whiteSpace: "nowrap" }}>
                  {period.due}
                </TableCell>
                {BUCKETS.map((bucket) => {
                  const value = bucket.value(pick(period));
                  const attention = bucket.unresolved === true && Number(value) !== 0;
                  return (
                    <TableCell
                      key={bucket.label}
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
    </Box>
  );
}
