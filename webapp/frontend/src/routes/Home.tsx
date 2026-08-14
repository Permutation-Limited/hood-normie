import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import Stack from "@mui/material/Stack";
import { Link } from "@tanstack/react-router";
import type { ReactElement } from "react";

/** Each card mirrors one of the command-line tools under //examples. */
const VIEWS = [
  {
    title: "Accounts",
    to: "/accounts",
    cta: "Open accounts",
    command: "bazel run //examples:list_accounts",
    description:
      "Every Robinhood brokerage account the authenticated token can read, with " +
      "its tax status, type, number, and nickname.",
  },
  {
    title: "Holdings",
    to: "/holdings",
    cta: "Open holdings",
    command: "bazel run //examples:list_holdings",
    description:
      "Each account's equity positions marked at the latest quote, with cash and " +
      "the account total.",
  },
  {
    title: "Rebalance",
    to: "/rebalance",
    cta: "Open rebalance",
    command: "bazel run //examples/rebalance",
    description:
      "Live positions and quotes, folded together with manually tracked external " +
      "accounts, showing the dollar adjustment per asset class each configured " +
      "portfolio needs to reach its target allocation.",
  },
] as const;

export default function Home(): ReactElement {
  return (
    <Box>
      <Typography variant="h5" gutterBottom>
        hood-normie
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 3 }}>
        A local, read-only view over Robinhood's official Trading MCP. Nothing here
        places an order.
      </Typography>
      <Stack spacing={2}>
        {VIEWS.map((view) => (
          <Card key={view.to} variant="outlined">
            <CardContent>
              <Typography variant="h6" gutterBottom>
                {view.title}
              </Typography>
              <Typography color="text.secondary" sx={{ mb: 1 }}>
                {view.description}
              </Typography>
              <Typography
                variant="body2"
                color="text.secondary"
                sx={{ mb: 2, fontFamily: "monospace" }}
              >
                {view.command}
              </Typography>
              <Button
                component={Link}
                to={view.to}
                // Keep demo mode on across the jump, as the header tabs do.
                search={true}
                variant="contained"
              >
                {view.cta}
              </Button>
            </CardContent>
          </Card>
        ))}
      </Stack>
    </Box>
  );
}
