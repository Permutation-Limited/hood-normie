import {
  createRootRoute,
  createRoute,
  createRouter,
  redirect,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import Accounts from "./routes/Accounts";
import Holdings from "./routes/Holdings";
import Home from "./routes/Home";
import Realized from "./routes/Realized";
import Unrealized from "./routes/Unrealized";
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

const performanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/performance",
  component: Realized,
});

const unrealizedRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/performance/unrealized",
  component: Unrealized,
});

// The tab was called Income before it gained unrealized gains; old links and
// bookmarks still land on it, demo flag and all.
const incomeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/income",
  beforeLoad: ({ search }) => {
    throw redirect({ to: "/performance", search });
  },
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  accountsRoute,
  holdingsRoute,
  rebalanceRoute,
  performanceRoute,
  unrealizedRoute,
  incomeRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
