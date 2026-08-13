import CssBaseline from "@mui/material/CssBaseline";
import useMediaQuery from "@mui/material/useMediaQuery";
import { ThemeProvider, createTheme } from "@mui/material/styles";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { StrictMode, useMemo } from "react";
import { createRoot } from "react-dom/client";
import { router } from "./router";
import type { ReactElement } from "react";

const queryClient = new QueryClient();

function App(): ReactElement {
  const prefersDark = useMediaQuery("(prefers-color-scheme: dark)");
  const theme = useMemo(
    () =>
      createTheme({
        palette: { mode: prefersDark ? "dark" : "light" },
        shape: { borderRadius: 8 },
      }),
    [prefersDark],
  );
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      <QueryClientProvider client={queryClient}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}

const container = document.getElementById("root");
if (!container) {
  throw new Error("index.html is missing the #root container");
}
createRoot(container).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
