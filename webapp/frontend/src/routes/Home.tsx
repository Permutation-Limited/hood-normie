import Box from "@mui/material/Box";
import Button from "@mui/material/Button";
import Card from "@mui/material/Card";
import CardContent from "@mui/material/CardContent";
import Typography from "@mui/material/Typography";
import { Link } from "@tanstack/react-router";
import type { ReactElement } from "react";

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
      <Card variant="outlined">
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Rebalance
          </Typography>
          <Typography color="text.secondary" sx={{ mb: 2 }}>
            Live positions and quotes, folded together with manually tracked external
            accounts, showing the dollar adjustment per asset class each configured
            portfolio needs to reach its target allocation.
          </Typography>
          <Button
            component={Link}
            to="/rebalance"
            search={true}
            variant="contained"
          >
            Open rebalance
          </Button>
        </CardContent>
      </Card>
    </Box>
  );
}
