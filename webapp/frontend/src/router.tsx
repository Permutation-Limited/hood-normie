import {
  createRootRoute,
  createRoute,
  createRouter,
} from "@tanstack/react-router";
import Layout from "./components/Layout";
import Home from "./routes/Home";
import Rebalance from "./routes/Rebalance";

const rootRoute = createRootRoute({ component: Layout });

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

const routeTree = rootRoute.addChildren([indexRoute, rebalanceRoute]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
