import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import type { ReactElement, ReactNode } from "react";

/**
 * The frame every data view shares: heading, errors, spinner.
 *
 * Refreshing and the demo indicator both live in the header, so a page never
 * repeats either one.
 */
export default function ReportPage({
  title,
  subtitle,
  notice,
  error,
  isFetching,
  hasData,
  loadingMessage,
  children,
}: {
  title: string;
  subtitle: string;
  notice?: ReactNode;
  error: unknown;
  isFetching: boolean;
  hasData: boolean;
  loadingMessage: string;
  children: ReactNode;
}): ReactElement {
  return (
    <Box>
      <Box sx={{ mb: 2 }}>
        <Typography variant="h5">{title}</Typography>
        <Typography variant="body2" color="text.secondary">
          {subtitle}
        </Typography>
      </Box>

      {notice && (
        <Alert severity="info" sx={{ mb: 3 }}>
          {notice}
        </Alert>
      )}

      {error != null && (
        <Alert severity="error" sx={{ mb: 3 }}>
          <AlertTitle>Could not load the data</AlertTitle>
          {error instanceof Error ? error.message : String(error)}
        </Alert>
      )}

      {isFetching && !hasData && (
        <Stack direction="row" spacing={2} alignItems="center" sx={{ py: 6 }}>
          <CircularProgress size={24} />
          <Typography color="text.secondary">{loadingMessage}</Typography>
        </Stack>
      )}

      {children}
    </Box>
  );
}
