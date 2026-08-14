import {
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import Accounts from "./routes/Accounts";
import Holdings from "./routes/Holdings";
import Home from "./routes/Home";
import Rebalance from "./routes/Rebalance";

/** Demo mode lives in the URL so a demo view is linkable and survives reload. */
export interface AppSearch {
  demo?: boolean;
}

function validateSearch(search: Record<string, unknown>): AppSearch {
  const value = search["demo"];
  const demo = value === true || value === "1" || value === "true";
  // Omitted rather than false, to keep a live URL free of query noise.
  return demo ? { demo: true } : {};
}

const rootRoute = createRootRoute({ component: Layout, validateSearch });

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Home,
});

const rebalanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/rebalance",
  component: Rebalance,
});

const accountsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/accounts",
  component: Accounts,
});

const holdingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/holdings",
  component: Holdings,
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  accountsRoute,
  holdingsRoute,
  rebalanceRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
