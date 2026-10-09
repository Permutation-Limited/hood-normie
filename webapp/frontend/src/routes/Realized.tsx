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
import PeriodsTable from "../components/PeriodsTable";
import PerformanceTabs from "../components/PerformanceTabs";
import ReportPage from "../components/ReportPage";
import SalesTable from "../components/SalesTable";
import TreatmentSummary from "../components/TreatmentSummary";
import WashSales from "../components/WashSales";
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
        {!account.tax_advantaged &&
          (account.sales.length > 0 || account.dividends.length > 0) && (
          <PeriodsTable
            periods={account.periods}
            account={account.label}
            demo={demo}
          />
        )}
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

/** The Performance tab's realized view: a year's gains and dividends. */
export default function Realized(): ReactElement {
  const [year, setYear] = useState<number>(THIS_YEAR);
  const { data, error, isFetching, isDemo } = useLiveQuery(
    `income-${String(year)}`,
    (options) => fetchIncome(year, options),
  );
  // Another year's snapshot may still be on screen while this one loads.
  const current = data?.year === year ? data : undefined;

  return (
    <ReportPage
      title="Performance"
      header={<PerformanceTabs />}
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
          Robinhood reports neither holding periods nor qualified status: a
          term is inferred from open lots or the order history, and qualified
          shares come from <code>income.yaml</code>. Reinvested dividends are
          exact; cash dividends are estimated from price history and dated by
          ex-date. Treat these as estimates, not a 1099.
        </>
      }
      error={error}
      isFetching={isFetching}
      hasData={Boolean(current)}
      loadingMessage={
        isDemo
          ? "Building the demo performance…"
          : "Fetching trades, orders, tax lots, and price history from Robinhood…"
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
              <TreatmentSummary
                treatment={current.taxable_treatment}
                carryoverShort={current.carryover_short}
                carryoverLong={current.carryover_long}
              />
              <Divider sx={{ my: 2 }} />
              <IncomeSummary totals={current.taxable_totals} />
              <PeriodsTable
                periods={current.taxable_periods}
                account="taxable"
                demo={current.demo}
              />
            </CardContent>
          </Card>
          <WashSales
            washSales={current.wash_sales}
            total={current.possibly_disallowed}
            demo={current.demo}
          />
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
