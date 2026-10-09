import Tab from "@mui/material/Tab";
import Tabs from "@mui/material/Tabs";
import { Link, useRouterState } from "@tanstack/react-router";
import type { ReactElement } from "react";

const VIEWS = [
  { label: "Realized & income", to: "/performance" },
  { label: "Unrealized", to: "/performance/unrealized" },
] as const;

/** Switches between the Performance tab's two views, each its own URL. */
export default function PerformanceTabs(): ReactElement {
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const active = VIEWS.some((view) => view.to === pathname) ? pathname : false;
  return (
    <Tabs value={active} sx={{ mb: 2, borderBottom: 1, borderColor: "divider" }}>
      {VIEWS.map((view) => (
        <Tab
          key={view.to}
          component={Link}
          to={view.to}
          // Keep demo mode on across the switch, as the header tabs do.
          search={true}
          value={view.to}
          label={view.label}
        />
      ))}
    </Tabs>
  );
}
