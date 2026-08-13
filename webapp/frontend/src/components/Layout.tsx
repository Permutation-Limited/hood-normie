import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Container from "@mui/material/Container";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Toolbar from "@mui/material/Toolbar";
import Typography from "@mui/material/Typography";
import { Link, Outlet, useRouterState } from "@tanstack/react-router";
import type { ReactElement } from "react";

const NAV = [
  { label: "Home", to: "/" },
  { label: "Rebalance", to: "/rebalance" },
] as const;

export default function Layout(): ReactElement {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  // Unknown paths must not select a tab, or MUI warns about an invalid value.
  const active = NAV.some((item) => item.to === pathname) ? pathname : false;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar position="static" color="default" elevation={0} sx={{ borderBottom: 1, borderColor: "divider" }}>
        <Toolbar sx={{ gap: 3 }}>
          <Typography variant="h6" sx={{ fontWeight: 700, letterSpacing: "-0.02em" }}>
            hood-normie
          </Typography>
          <Tabs value={active} sx={{ minHeight: 0 }}>
            {NAV.map((item) => (
              <Tab
                key={item.to}
                component={Link}
                to={item.to}
                value={item.to}
                label={item.label}
              />
            ))}
          </Tabs>
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4, flexGrow: 1 }}>
        <Outlet />
      </Container>
    </Box>
  );
}
