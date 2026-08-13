import Accordion from "@mui/material/Accordion";
import AccordionDetails from "@mui/material/AccordionDetails";
import AccordionSummary from "@mui/material/AccordionSummary";
import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import CircularProgress from "@mui/material/CircularProgress";
import Divider from "@mui/material/Divider";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ExpandMoreIcon from "@mui/icons-material/ExpandMore";
import RefreshIcon from "@mui/icons-material/Refresh";
import { useQuery } from "@tanstack/react-query";
import type { Portfolio } from "../api";
import { fetchRebalance } from "../api";
import { money } from "../format";
import AccountTable from "../components/AccountTable";
import PlanTable from "../components/PlanTable";
import type { ReactElement } from "react";

function PortfolioSection({ portfolio }: { portfolio: Portfolio }): ReactElement {
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

        <PlanTable recommendations={portfolio.recommendations} />

        <Accordion variant="outlined" disableGutters sx={{ mt: 2 }}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Typography variant="subtitle2">
              Holdings ({portfolio.accounts.length}{" "}
              {portfolio.accounts.length === 1 ? "account" : "accounts"})
            </Typography>
          </AccordionSummary>
          <AccordionDetails>
            {portfolio.accounts.map((account) => (
              <AccountTable key={account.label} account={account} />
            ))}
          </AccordionDetails>
        </Accordion>
      </CardContent>
    </Card>
  );
}

export default function Rebalance(): ReactElement {
  const { data, error, isFetching, refetch } = useQuery({
    queryKey: ["rebalance"],
    queryFn: ({ signal }) => fetchRebalance(signal),
    // Quotes are live: every view is a fresh snapshot, never a cached one.
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });

  return (
    <Box>
      <Stack
        direction="row"
        justifyContent="space-between"
        alignItems="center"
        sx={{ mb: 2 }}
      >
        <Box>
          <Typography variant="h5">Rebalance</Typography>
          <Typography variant="body2" color="text.secondary">
            {data
              ? `Snapshot taken ${new Date(data.generated_at).toLocaleString()}`
              : "Live Robinhood quotes and positions"}
          </Typography>
        </Box>
        <Button
          variant="outlined"
          startIcon={isFetching ? <CircularProgress size={16} /> : <RefreshIcon />}
          onClick={() => void refetch()}
          disabled={isFetching}
        >
          {isFetching ? "Fetching" : "Refresh"}
        </Button>
      </Stack>

      <Alert severity="info" sx={{ mb: 3 }}>
        Read-only. These are class-level dollar amounts, not orders — the tool does
        not choose a security and never places a trade.
      </Alert>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <AlertTitle>Could not build the report</AlertTitle>
          {error instanceof Error ? error.message : String(error)}
        </Alert>
      )}

      {isFetching && !data && (
        <Stack direction="row" spacing={2} alignItems="center" sx={{ py: 6 }}>
          <CircularProgress size={24} />
          <Typography color="text.secondary">
            Fetching live positions and quotes from Robinhood…
          </Typography>
        </Stack>
      )}

      {data?.portfolios.map((portfolio) => (
        <PortfolioSection key={portfolio.name} portfolio={portfolio} />
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
    </Box>
  );
}
