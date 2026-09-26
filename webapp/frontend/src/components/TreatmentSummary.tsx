import Box from "@mui/material/Box";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { Treatment, TreatmentRange } from "../api";
import { money } from "../format";
import type { ReactElement } from "react";

/** Two amounts as an ascending range. */
function span(low: string, high: string): string {
  const [first, second] =
    Number(low) <= Number(high) ? [low, high] : [high, low];
  return `${money(first)} to ${money(second)}`;
}

function Rate({
  label,
  detail,
  pick,
  range,
}: {
  label: string;
  detail: string;
  pick: (treatment: Treatment) => string;
  range: TreatmentRange;
}): ReactElement {
  // With nothing unresolved the two scenarios agree. Otherwise the range is
  // the headline: leaving unresolved amounts out is not itself a possible
  // outcome, since netting lets an unknown gain move the other line too.
  const low = pick(range.all_ordinary);
  const high = pick(range.all_preferential);
  const settled = Number(low) === Number(high);
  return (
    <Box sx={{ flex: 1, minWidth: 0 }}>
      <Typography variant="body2" color="text.secondary">
        {label}
      </Typography>
      <Typography
        variant="h5"
        color={settled ? undefined : "warning.main"}
        sx={{ fontVariantNumeric: "tabular-nums" }}
      >
        {settled ? money(low) : span(low, high)}
      </Typography>
      <Typography variant="caption" color="text.secondary" component="p">
        {detail}
      </Typography>
    </Box>
  );
}

/**
 * The taxable accounts' income grouped by tax rate: the two numbers an
 * estimate starts from. Losses net across accounts and the $3,000 limit is per
 * return, so this is only shown for the taxable total, never per account.
 */
export default function TreatmentSummary({
  treatment,
  carryoverShort,
  carryoverLong,
}: {
  treatment: TreatmentRange;
  carryoverShort: string;
  carryoverLong: string;
}): ReactElement {
  const { all_ordinary: low, all_preferential: high } = treatment;
  const amount = (pick: (t: Treatment) => string): string =>
    Number(pick(low)) === Number(pick(high))
      ? money(pick(low))
      : span(pick(low), pick(high));
  const deducted = Math.max(Number(low.deductible_loss), Number(high.deductible_loss));
  const carried = Math.max(Number(low.carryforward), Number(high.carryforward));
  const carriedIn = Number(carryoverShort) + Number(carryoverLong);
  return (
    <Box>
      <Typography variant="overline" color="text.secondary">
        By tax rate, after netting gains and losses
      </Typography>
      <Stack direction={{ xs: "column", sm: "row" }} spacing={3} sx={{ mb: 1 }}>
        <Rate
          label="Ordinary rates"
          detail="Short-term gains and non-qualified dividends, taxed like wages"
          pick={(t) => t.ordinary}
          range={treatment}
        />
        <Rate
          label="Preferential rates"
          detail="Long-term gains and qualified dividends, taxed at 0/15/20%"
          pick={(t) => t.preferential}
          range={treatment}
        />
      </Stack>
      {(Number(treatment.unresolved_gains) !== 0 ||
        Number(treatment.unresolved_dividends) !== 0) && (
        <Typography variant="body2" color="warning.main">
          Ranges run from every unresolved amount at ordinary rates to every one
          at preferential rates: {money(treatment.unresolved_gains)} of gains
          with an unknown holding period and{" "}
          {money(treatment.unresolved_dividends)} of unclassified dividends.
        </Typography>
      )}
      {deducted > 0 && (
        <Typography variant="body2" color="text.secondary">
          Ordinary income includes a {amount((t) => t.deductible_loss)} net
          capital loss deduction
          {carried > 0 &&
            `; ${amount((t) => t.carryforward)} more carries into next year`}
          .
        </Typography>
      )}
      {carriedIn > 0 && (
        <Typography variant="body2" color="text.secondary">
          Includes last year&apos;s loss carryover of{" "}
          {money(String(carriedIn))} from <code>income.yaml</code>.
        </Typography>
      )}
    </Box>
  );
}
