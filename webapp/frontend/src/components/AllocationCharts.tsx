import Box from "@mui/material/Box";
import Breadcrumbs from "@mui/material/Breadcrumbs";
import Link from "@mui/material/Link";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import type { Portfolio } from "../api";
import {
  UNCLASSIFIED,
  classBySymbol,
  classSlots,
  currentByClass,
  targetByClass,
} from "../allocation";
import AllocationDonut from "./AllocationDonut";
import { useMemo, useState } from "react";
import type { ReactElement } from "react";

/** The scope value for the whole portfolio; any other value is an account label. */
const PORTFOLIO = "";

/**
 * A portfolio's allocation as donuts: by asset class now and as the plan
 * targets it, for the whole portfolio or one account. Opening a class shows the
 * symbols that make it up within the chosen scope.
 */
export default function AllocationCharts({
  portfolio,
}: {
  portfolio: Portfolio;
}): ReactElement {
  const [scope, setScope] = useState(PORTFOLIO);
  const [opened, setOpened] = useState<string | null>(null);

  const slots = useMemo(() => classSlots(portfolio.recommendations), [portfolio]);
  const accounts = useMemo(
    () =>
      scope === PORTFOLIO
        ? portfolio.accounts
        : portfolio.accounts.filter((account) => account.label === scope),
    [portfolio, scope],
  );
  const current = useMemo(() => currentByClass(accounts, slots), [accounts, slots]);
  const target = useMemo(
    () => targetByClass(portfolio.recommendations, slots),
    [portfolio, slots],
  );

  // A class the new scope does not hold has nothing to open, so fall back.
  const shown =
    opened !== null && current.slices.some((slice) => slice.key === opened) ? opened : null;
  const symbols = useMemo(
    () => (shown === null ? null : classBySymbol(accounts, shown)),
    [accounts, shown],
  );
  const scopeName = scope === PORTFOLIO ? "Portfolio" : scope;

  return (
    <Box sx={{ mb: 3 }}>
      {portfolio.accounts.length > 1 && (
        <ToggleButtonGroup
          size="small"
          exclusive
          value={scope}
          onChange={(_event, value: string | null) => value !== null && setScope(value)}
          aria-label="Allocation scope"
          sx={{ mb: 2, flexWrap: "wrap" }}
        >
          <ToggleButton value={PORTFOLIO}>Portfolio</ToggleButton>
          {portfolio.accounts.map((account) => (
            <ToggleButton key={account.label} value={account.label}>
              {account.label}
            </ToggleButton>
          ))}
        </ToggleButtonGroup>
      )}
      <Stack direction={{ xs: "column", lg: "row" }} spacing={4}>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          {symbols === null || shown === null ? (
            // Keyed so a level starts with nothing highlighted: the row that
            // was clicked to open it no longer exists.
            <AllocationDonut
              key={`${scope}\0classes`}
              title={`${scopeName} · current`}
              allocation={current}
              onOpen={setOpened}
              empty="No holdings or cash"
            />
          ) : (
            <AllocationDonut
              key={`${scope}\0${shown}`}
              title={
                <Breadcrumbs aria-label="Allocation level">
                  <Link
                    component="button"
                    variant="subtitle2"
                    underline="hover"
                    onClick={() => setOpened(null)}
                  >
                    {scopeName} · current
                  </Link>
                  <Typography variant="subtitle2" color="text.primary">
                    {shown === UNCLASSIFIED ? "unclassified symbols" : shown}
                  </Typography>
                </Breadcrumbs>
              }
              allocation={symbols}
              empty="No holdings in this class"
            />
          )}
        </Box>
        {/* Targets are set per portfolio, so an account has none of its own. */}
        {scope === PORTFOLIO && (
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <AllocationDonut title="Portfolio · target" allocation={target} />
          </Box>
        )}
      </Stack>
    </Box>
  );
}
