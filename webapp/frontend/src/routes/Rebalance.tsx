import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import type { Portfolio } from "../api";
import { fetchRebalance } from "../api";
import { money } from "../format";
import AccountTable from "../components/AccountTable";
import PlanTable from "../components/PlanTable";
import ReportPage from "../components/ReportPage";
import { useLiveQuery } from "../useLiveQuery";
import type { ReactElement } from "react";

function PortfolioSection({
  portfolio,
  demo,
}: {
  portfolio: Portfolio;
  demo: boolean;
}): ReactElement {
  return (
    <Card variant="outlined" sx={{ mb: 3 }}>
      <CardContent>
        <Stack
          direction="row"
          justifyContent="space-between"
          alignItems="baseline"
          sx={{ mb: 2 }}
        >
          <Typography variant="h6">{portfolio.name}</Typography>
          <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>
            {money(portfolio.total_value)}
          </Typography>
        </Stack>
        <Typography variant="body2" color="text.secondary" sx={{ mb: 2 }}>
          Target cash {money(portfolio.target_cash)} · minimum trade{" "}
          {money(portfolio.minimum_trade)}
        </Typography>

        {portfolio.unclassified.length > 0 && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            <AlertTitle>Unclassified assets are implicitly ignored</AlertTitle>
            <Box component="ul" sx={{ m: 0, pl: 3 }}>
              {portfolio.unclassified.map((position) => (
                <li key={position.symbol}>
                  {position.symbol}: {money(position.market_value)}
                </li>
              ))}
            </Box>
            Their value is removed from the allocation base and no trade is assumed.
            Map a symbol to a non-ignored class if it should affect targets.
          </Alert>
        )}

        <PlanTable
          recommendations={portfolio.recommendations}
          portfolio={portfolio.name}
          demo={demo}
        />

        <Accordion variant="outlined" disableGutters sx={{ mt: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              Holdings ({portfolio.accounts.length}{" "}
              {portfolio.accounts.length === 1 ? "account" : "accounts"})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {portfolio.accounts.map((account) => (
              <AccountTable
                key={account.label}
                account={account}
                demo={demo}
              />
            ))}
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
}

export default function Rebalance(): ReactElement {
  const { data, error, isFetching, isDemo } = useLiveQuery(
    "rebalance",
    fetchRebalance,
  );

  return (
    <ReportPage
      title="Rebalance"
      subtitle={
        data
          ? `Snapshot taken ${new Date(data.generated_at).toLocaleString()}`
          : isDemo
            ? "Invented portfolios, no account contacted"
            : "Live Robinhood quotes and positions"
      }
      notice="Read-only. These are class-level dollar amounts, not orders — the tool
        does not choose a security and never places a trade."
      error={error}
      isFetching={isFetching}
      hasData={Boolean(data)}
      loadingMessage={
        isDemo
          ? "Building the demo report…"
          : "Fetching live positions and quotes from Robinhood…"
      }
    >
      {data?.portfolios.map((portfolio) => (
        <PortfolioSection
          key={portfolio.name}
          portfolio={portfolio}
          demo={data.demo}
        />
      ))}

      {data && data.portfolios.length > 1 && (
        <>
          <Divider sx={{ mb: 2 }} />
          <Stack direction="row" justifyContent="space-between" sx={{ px: 1 }}>
            <Typography variant="h6">All portfolios</Typography>
            <Typography variant="h6" sx={{ fontVariantNumeric: "tabular-nums" }}>
              {money(data.grand_total)}
            </Typography>
          </Stack>
        </>
      )}
    </ReportPage>
  );
}
