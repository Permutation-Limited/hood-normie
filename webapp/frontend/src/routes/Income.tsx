import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import ToggleButton from "@mui/material/ToggleButton";
import ToggleButtonGroup from "@mui/material/ToggleButtonGroup";
import Typography from "@mui/material/Typography";
import { useState } from "react";
import type { IncomeAccount } from "../api";
import { fetchIncome } from "../api";
import DividendsTable from "../components/DividendsTable";
import IncomeSummary from "../components/IncomeSummary";
import ReportPage from "../components/ReportPage";
import SalesTable from "../components/SalesTable";
import { useLiveQuery } from "../useLiveQuery";
import type { ReactElement } from "react";

const THIS_YEAR = new Date().getFullYear();
// The current year for estimated payments, plus the two before it for a
// January catch-up or a look back.
const YEARS = [THIS_YEAR, THIS_YEAR - 1, THIS_YEAR - 2] as const;

function AccountSection({
  account,
  demo,
}: {
  account: IncomeAccount;
  demo: boolean;
}): ReactElement {
  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Stack
          direction="row"
          spacing={1}
          alignItems="center"
          flexWrap="wrap"
          useFlexGap
          sx={{ mb: 2 }}
        >
          <Typography variant="h6">{account.label}</Typography>
          <Chip
            size="small"
            variant="outlined"
            label={account.tax_advantaged ? "Tax-advantaged" : "Taxable"}
          />
        </Stack>
        <IncomeSummary
          totals={account.totals}
          taxAdvantaged={account.tax_advantaged}
        />
        <Divider sx={{ my: 2 }} />
        <SalesTable
          sales={account.sales}
          account={account.label}
          taxAdvantaged={account.tax_advantaged}
          demo={demo}
        />
        <DividendsTable
          dividends={account.dividends}
          totals={account.totals}
          account={account.label}
          demo={demo}
        />
      </CardContent>
    </Card>
  );
}

export default function Income(): ReactElement {
  const [year, setYear] = useState<number>(THIS_YEAR);
  const { data, error, isFetching, isDemo } = useLiveQuery(
    `income-${String(year)}`,
    (options) => fetchIncome(year, options),
  );
  // Another year's snapshot may still be on screen while this one loads.
  const current = data?.year === year ? data : undefined;

  return (
    <ReportPage
      title="Income"
      subtitle={
        current
          ? `Fetched ${new Date(current.generated_at).toLocaleString()}`
          : isDemo
            ? "Invented trades and dividends, no account contacted"
            : "Realized gains and reinvested dividends from Robinhood"
      }
      notice={
        <>
          Sorted into the buckets a tax estimate needs; no tax is computed.
          Robinhood reports neither holding periods nor qualified status, so a
          term is inferred only when an older lot is still open, and qualified
          shares come from <code>income.yaml</code>. Only reinvested dividends
          are visible. Treat these as estimates, not a 1099.
        </>
      }
      error={error}
      isFetching={isFetching}
      hasData={Boolean(current)}
      loadingMessage={
        isDemo
          ? "Building the demo income…"
          : "Fetching trades, orders, and tax lots from Robinhood…"
      }
    >
      <ToggleButtonGroup
        exclusive
        size="small"
        value={year}
        onChange={(_, value: number | null) => {
          if (value !== null) {
            setYear(value);
          }
        }}
        aria-label="Tax year"
        sx={{ mb: 3 }}
      >
        {YEARS.map((item) => (
          <ToggleButton key={item} value={item}>
            {item}
          </ToggleButton>
        ))}
      </ToggleButtonGroup>

      {current && (
        <>
          <Card variant="outlined" sx={{ mb: 3 }}>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Taxable accounts
              </Typography>
              <IncomeSummary totals={current.taxable_totals} />
            </CardContent>
          </Card>
          {current.accounts.map((account) => (
            <AccountSection
              key={account.account_number}
              account={account}
              demo={current.demo}
            />
          ))}
        </>
      )}
    </ReportPage>
  );
}
