import AppBar from "@mui/material/AppBar";
import Box from "@mui/material/Box";
import Chip from "@mui/material/Chip";
import CircularProgress from "@mui/material/CircularProgress";
import Container from "@mui/material/Container";
import IconButton from "@mui/material/IconButton";
import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import Toolbar from "@mui/material/Toolbar";
import Tooltip from "@mui/material/Tooltip";
import Typography from "@mui/material/Typography";
import RefreshIcon from "@mui/icons-material/Refresh";
import ScienceIcon from "@mui/icons-material/Science";
import { useIsFetching, useQueryClient } from "@tanstack/react-query";
import { Link, Outlet, useRouterState, useSearch } from "@tanstack/react-router";
import type { ReactElement } from "react";
import DemoSwitch from "./DemoSwitch";

const NAV = [
  { label: "Home", to: "/" },
  { label: "Accounts", to: "/accounts" },
  { label: "Holdings", to: "/holdings" },
  { label: "Rebalance", to: "/rebalance" },
] as const;

export default function Layout(): ReactElement {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const { demo } = useSearch({ strict: false });
  const queryClient = useQueryClient();
  const fetching = useIsFetching() > 0;
  // Unknown paths must not select a tab, or MUI warns about an invalid value.
  const active = NAV.some((item) => item.to === pathname) ? pathname : false;

  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <AppBar
        position="static"
        color="default"
        elevation={0}
        sx={{ borderBottom: 1, borderColor: "divider" }}
      >
        <Toolbar sx={{ gap: { xs: 1, sm: 3 } }}>
          <Typography
            variant="h6"
            sx={{
              fontWeight: 700,
              letterSpacing: "-0.02em",
              // The header is a single row; the title must not wrap or squeeze
              // the tabs when the demo controls are present on a narrow window.
              whiteSpace: "nowrap",
              flexShrink: 0,
              fontSize: { xs: "1rem", sm: "1.25rem" },
            }}
          >
            hood-normie
          </Typography>
          <Tabs
            value={active}
            variant="scrollable"
            scrollButtons="auto"
            allowScrollButtonsMobile
            // Without scrolling, a narrow window clips a tab out of reach.
            sx={{ minHeight: 0, minWidth: 0 }}
          >
            {NAV.map((item) => (
              <Tab
                key={item.to}
                component={Link}
                to={item.to}
                // Carry demo mode across navigation; losing it mid-session would
                // silently swap invented numbers for real ones.
                search={true}
                value={item.to}
                label={item.label}
              />
            ))}
          </Tabs>
          <Box sx={{ flexGrow: 1 }} />
          <Tooltip title="Refresh every view">
            {/* A disabled button fires no events, so the tooltip needs a live
                wrapper to hang off while a fetch is in flight. */}
            <span>
              <IconButton
                size="small"
                aria-label="Refresh every view"
                disabled={fetching}
                // Discards every cached snapshot, not just this tab's: the
                // header belongs to all of them, so a refresh here must not
                // leave another tab holding older numbers.
                onClick={() => void queryClient.invalidateQueries()}
              >
                {fetching ? <CircularProgress size={20} /> : <RefreshIcon />}
              </IconButton>
            </span>
          </Tooltip>
          {demo && (
            <Chip
              icon={<ScienceIcon />}
              label="Demo data"
              color="warning"
              size="small"
              // Redundant on small screens: the switch is right beside it and
              // the page itself carries a full demo banner.
              sx={{ display: { xs: "none", sm: "flex" } }}
            />
          )}
          <DemoSwitch demo={Boolean(demo)} />
        </Toolbar>
      </AppBar>
      <Container maxWidth="lg" sx={{ py: 4, flexGrow: 1 }}>
        <Outlet />
      </Container>
    </Box>
  );
}
