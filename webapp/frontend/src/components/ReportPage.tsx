import Alert from "@mui/material/Alert";
import AlertTitle from "@mui/material/AlertTitle";
import Box from "@mui/material/Box";
import CircularProgress from "@mui/material/CircularProgress";
import Stack from "@mui/material/Stack";
import Typography from "@mui/material/Typography";
import ScienceIcon from "@mui/icons-material/Science";
import type { ReactElement, ReactNode } from "react";

/**
 * The frame every data view shares: heading, demo banner, errors, spinner.
 *
 * Refreshing lives in the header, since it refetches every view at once.
 *
 * `demo` is the flag from the response rather than the URL, so the banner
 * always describes what the server actually computed.
 */
export default function ReportPage({
  title,
  subtitle,
  demo,
  notice,
  error,
  isFetching,
  hasData,
  loadingMessage,
  children,
}: {
  title: string;
  subtitle: string;
  demo: boolean;
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

      {demo ? (
        <Alert severity="warning" icon={<ScienceIcon />} sx={{ mb: 3 }}>
          <AlertTitle>Demo data</AlertTitle>
          Invented accounts and quotes. No Robinhood account was contacted and none
          of these figures are yours. Turn off Demo in the header for live accounts.
        </Alert>
      ) : (
        notice && (
          <Alert severity="info" sx={{ mb: 3 }}>
            {notice}
          </Alert>
        )
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
