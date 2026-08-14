import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import { fetchHoldings } from "../api";
import { money } from "../format";
import HoldingsTable from "../components/HoldingsTable";
import ReportPage from "../components/ReportPage";
import { useLiveQuery } from "../useLiveQuery";
import type { ReactElement } from "react";

export default function Holdings(): ReactElement {
  const { data, error, isFetching, isDemo } = useLiveQuery(
    "holdings",
    fetchHoldings,
  );

  return (
    <ReportPage
      title="Holdings"
      subtitle={
        data
          ? `Snapshot taken ${new Date(data.generated_at).toLocaleString()}`
          : isDemo
            ? "Invented positions, no account contacted"
            : "Live Robinhood positions and quotes"
      }
      demo={Boolean(data?.demo)}
      notice="Equity positions only, marked at the latest quote. Options, crypto, and
        anything held outside Robinhood are not shown here."
      error={error}
      isFetching={isFetching}
      hasData={Boolean(data)}
      loadingMessage={
        isDemo
          ? "Building the demo holdings…"
          : "Fetching live positions and quotes from Robinhood…"
      }
    >
      {data?.accounts.map((account) => (
        <HoldingsTable key={account.label} account={account} />
      ))}

      {data && data.accounts.length > 1 && (
        <>
          <Divider sx={{ mb: 2 }} />
          <Stack direction="row" justifyContent="space-between" sx={{ px: 1 }}>
            <Typography variant="h6">All accounts</Typography>
            <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>
              {money(data.grand_total)}
            </Typography>
          </Stack>
        </>
      )}
    </ReportPage>
  );
}
