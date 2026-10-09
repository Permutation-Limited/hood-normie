import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Chip from "@mui/material/Chip";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { UnrealizedAccount, UnrealizedTotals } from "../api";
import { fetchUnrealized } from "../api";
import { money } from "../format";
import PerformanceTabs from "../components/PerformanceTabs";
import ReportPage from "../components/ReportPage";
import UnrealizedTable from "../components/UnrealizedTable";
import { useLiveQuery } from "../useLiveQuery";
import type { ReactElement } from "react";

const percent = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
  signDisplay: "exceptZero",
});

function Figures({ totals }: { totals: UnrealizedTotals }): ReactElement {
  const gain = Number(totals.unrealized);
  const color = gain > 0 ? "success.main" : gain < 0 ? "error.main" : undefined;
  return (
    <Stack direction="row" spacing={4} flexWrap="wrap" useFlexGap sx={{ mb: 2 }}>
      <Box>
        <Typography variant="body2" color="text.secondary">
          Market value
        </Typography>
        <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>
          {money(totals.market_value)}
        </Typography>
      </Box>
      <Box>
        <Typography variant="body2" color="text.secondary">
          Cost basis
        </Typography>
        <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>
          {money(totals.cost_basis)}
        </Typography>
      </Box>
      <Box>
        <Typography variant="body2" color="text.secondary">
          Unrealized gain
        </Typography>
        <Typography variant="h6" color={color} sx={{ fontVariantNumeric: "tabular-nums" }}>
          {money(totals.unrealized)}
          {totals.return_rate !== null &&
            ` (${percent.format(Number(totals.return_rate))})`}
        </Typography>
      </Box>
    </Stack>
  );
}

function AccountSection({
  account,
  demo,
}: {
  account: UnrealizedAccount;
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
        <Figures totals={account.totals} />
        <UnrealizedTable
          holdings={account.holdings}
          totals={account.totals}
          name={account.label}
          demo={demo}
        />
      </CardContent>
    </Card>
  );
}

/** The Performance tab's unrealized view: today's gains on what is still held. */
export default function Unrealized(): ReactElement {
  const { data, error, isFetching, isDemo } = useLiveQuery(
    "unrealized",
    fetchUnrealized,
  );
  const taxable = data?.accounts.filter((account) => !account.tax_advantaged) ?? [];

  return (
    <ReportPage
      title="Performance"
      header={<PerformanceTabs />}
      subtitle={
        data
          ? `Marked ${new Date(data.generated_at).toLocaleString()}`
          : isDemo
            ? "Invented holdings, no account contacted"
            : "Live positions, quotes, and tax lots from Robinhood"
      }
      notice={
        <>
          Each holding is marked at the latest quote against the cost basis of
          its open tax lots — the basis Robinhood reports on a 1099-B, wash-sale
          adjustments included. Holding periods are not considered. Retirement
          accounts are listed but left out of the taxable total.
        </>
      }
      error={error}
      isFetching={isFetching}
      hasData={Boolean(data)}
      loadingMessage={
        isDemo
          ? "Building the demo holdings…"
          : "Fetching positions, quotes, and tax lots from Robinhood…"
      }
    >
      {data && taxable.length > 0 && (
        <Card variant="outlined" sx={{ mb: 3 }}>
          <CardContent>
            <Typography variant="h6" gutterBottom>
              Taxable accounts combined
            </Typography>
            <Figures totals={data.taxable_totals} />
            {taxable.length > 1 && (
              <UnrealizedTable
                holdings={data.combined}
                totals={data.taxable_totals}
                name="taxable"
                demo={data.demo}
              />
            )}
          </CardContent>
        </Card>
      )}
      {data?.accounts.map((account) => (
        <AccountSection key={account.account_number} account={account} demo={data.demo} />
      ))}
    </ReportPage>
  );
}
