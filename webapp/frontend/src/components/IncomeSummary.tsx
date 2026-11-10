import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { IncomeTotals } from "../api";
import { money } from "../format";
import type { ReactElement } from "react";

interface Figure {
  label: string;
  value: string;
  /** An amount that still needs classifying before it can be estimated. */
  unresolved?: boolean;
}

function FigureGroup({
  title,
  figures,
  note,
}: {
  title: string;
  figures: readonly Figure[];
  note?: string | undefined;
}): ReactElement {
  return (
    <Box sx={{ flex: 1, minWidth: 0 }}>
      <Typography variant="overline" color="text.secondary">
        {title}
      </Typography>
      <Stack
        direction="row"
        spacing={3}
        flexWrap="wrap"
        useFlexGap
        sx={{ rowGap: 1 }}
      >
        {figures.map((figure) => {
          const attention = figure.unresolved === true && Number(figure.value) !== 0;
          return (
            <Box key={figure.label}>
              <Typography
                variant="body2"
                color={attention ? "warning.main" : "text.secondary"}
              >
                {figure.label}
              </Typography>
              <Typography
                variant="h6"
                color={attention ? "warning.main" : undefined}
                sx={{ fontVariantNumeric: "tabular-nums" }}
              >
                {money(figure.value)}
              </Typography>
            </Box>
          );
        })}
      </Stack>
      {note && (
        <Typography variant="caption" color="text.secondary">
          {note}
        </Typography>
      )}
    </Box>
  );
}

/** Says how much of the dividends shown are estimates rather than reported. */
function cashNote(totals: IncomeTotals): string | undefined {
  return Number(totals.estimated_cash) === 0
    ? undefined
    : `Includes ${money(totals.estimated_cash)} of cash dividends estimated from price history`;
}

/** Realized gains plus dividends, as the API's decimal strings. */
function combined(totals: IncomeTotals): string {
  return (Number(totals.realized) + Number(totals.dividends)).toFixed(2);
}

function Headline({
  label,
  value,
}: {
  label: string;
  value: string;
}): ReactElement {
  return (
    <Box>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography
        variant="h4"
        color={Number(value) < 0 ? "error.main" : undefined}
        sx={{ fontVariantNumeric: "tabular-nums" }}
      >
        {money(value)}
      </Typography>
    </Box>
  );
}

/**
 * What the year actually produced: the figures Robinhood reports or that
 * follow directly from its orders, with no guess at how they will be taxed.
 */
export default function IncomeSummary({
  totals,
}: {
  totals: IncomeTotals;
}): ReactElement {
  const note = cashNote(totals);
  return (
    <Box>
      <Stack
        direction="row"
        spacing={5}
        flexWrap="wrap"
        useFlexGap
        sx={{ rowGap: 1 }}
      >
        <Headline label="Realized gains" value={totals.realized} />
        <Headline label="Dividends" value={totals.dividends} />
        <Headline label="Total" value={combined(totals)} />
      </Stack>
      {note && (
        <Typography variant="caption" color="text.secondary">
          {note}
        </Typography>
      )}
    </Box>
  );
}

/**
 * The buckets a tax estimate asks for. These are inferences, not broker
 * figures: terms assume FIFO lot relief, and qualified shares come from
 * `income.yaml`.
 */
export function IncomeBreakdown({
  totals,
}: {
  totals: IncomeTotals;
}): ReactElement {
  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
      <FigureGroup
        title="Realized gains by inferred term"
        figures={[
          { label: "Short-term", value: totals.short_term },
          { label: "Long-term", value: totals.long_term },
          { label: "Unknown term", value: totals.unknown_term, unresolved: true },
        ]}
      />
      <FigureGroup
        title="Dividends by qualification"
        figures={[
          { label: "Qualified", value: totals.qualified },
          { label: "Non-qualified", value: totals.nonqualified },
          { label: "Unclassified", value: totals.unclassified, unresolved: true },
        ]}
      />
    </Stack>
  );
}
