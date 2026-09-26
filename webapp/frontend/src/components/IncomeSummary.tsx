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
}: {
  title: string;
  figures: readonly Figure[];
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
    </Box>
  );
}

/**
 * The buckets a tax estimate asks for. A retirement account has only totals:
 * neither its holding periods nor its qualified share are taxed this year.
 */
export default function IncomeSummary({
  totals,
  taxAdvantaged = false,
}: {
  totals: IncomeTotals;
  taxAdvantaged?: boolean;
}): ReactElement {
  if (taxAdvantaged) {
    return (
      <FigureGroup
        title="Not taxed this year"
        figures={[
          { label: "Realized gains", value: totals.realized },
          { label: "Dividends", value: totals.dividends },
        ]}
      />
    );
  }
  return (
    <Stack direction={{ xs: "column", md: "row" }} spacing={3}>
      <FigureGroup
        title="Realized gains"
        figures={[
          { label: "Short-term", value: totals.short_term },
          { label: "Long-term", value: totals.long_term },
          { label: "Unknown term", value: totals.unknown_term, unresolved: true },
        ]}
      />
      <FigureGroup
        title="Dividends"
        figures={[
          { label: "Qualified", value: totals.qualified },
          { label: "Non-qualified", value: totals.nonqualified },
          { label: "Unclassified", value: totals.unclassified, unresolved: true },
        ]}
      />
    </Stack>
  );
}
