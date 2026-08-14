import Paper from "@mui/material/Paper";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import { fetchAccounts } from "../api";
import ReportPage from "../components/ReportPage";
import { useLiveQuery } from "../useLiveQuery";
import type { ReactElement } from "react";

/** Robinhood omits fields freely; the CLI prints "(unavailable)" for them. */
function Field({ value }: { value: string | null }): ReactElement {
  if (value === null) {
    return (
      <Typography variant="body2" color="text.disabled">
        unavailable
      </Typography>
    );
  }
  return <>{value}</>;
}

export default function Accounts(): ReactElement {
  const { data, error, isFetching, refetch, isDemo } = useLiveQuery(
    "accounts",
    fetchAccounts,
  );

  return (
    <ReportPage
      title="Accounts"
      subtitle={
        data
          ? `Fetched ${new Date(data.generated_at).toLocaleString()}`
          : isDemo
            ? "Invented accounts, no account contacted"
            : "Every Robinhood account this token can read"
      }
      demo={Boolean(data?.demo)}
      error={error}
      isFetching={isFetching}
      hasData={Boolean(data)}
      loadingMessage={
        isDemo ? "Building the demo account list…" : "Fetching your accounts…"
      }
      onRefresh={() => void refetch()}
    >
      {data && (
        <TableContainer component={Paper} variant="outlined">
          <Table size="small">
            <TableHead>
              <TableRow>
                <TableCell>Tax status</TableCell>
                <TableCell>Type</TableCell>
                <TableCell>Account number</TableCell>
                <TableCell>Nickname</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {data.accounts.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4}>
                    <Typography variant="body2" color="text.secondary">
                      No Robinhood accounts found.
                    </Typography>
                  </TableCell>
                </TableRow>
              )}
              {data.accounts.map((account, index) => (
                <TableRow key={account.account_number ?? `row-${String(index)}`} hover>
                  <TableCell>
                    <Field value={account.tax_status} />
                  </TableCell>
                  <TableCell>
                    <Field value={account.account_type} />
                  </TableCell>
                  <TableCell sx={{ fontWeight: 500 }}>
                    <Field value={account.account_number} />
                  </TableCell>
                  <TableCell>
                    <Field value={account.nickname} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}
    </ReportPage>
  );
}
