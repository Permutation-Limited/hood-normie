import Paper from "@mui/material/Paper";
import Stack from "@mui/material/Stack";
import Table from "@mui/material/Table";
import TableBody from "@mui/material/TableBody";
import TableCell from "@mui/material/TableCell";
import TableContainer from "@mui/material/TableContainer";
import TableRow from "@mui/material/TableRow";
import Typography from "@mui/material/Typography";
import type { AccountSummary } from "../api";
import { fetchAccounts } from "../api";
import CsvButton from "../components/CsvButton";
import ReportPage from "../components/ReportPage";
import SortableHead from "../components/SortableHead";
import TableSearch from "../components/TableSearch";
import type { Column } from "../sorting";
import { useLiveQuery } from "../useLiveQuery";
import { useTableView } from "../useTableView";
import type { ReactElement } from "react";

const COLUMNS: readonly Column<AccountSummary>[] = [
  { id: "tax_status", label: "Tax status", value: (row) => row.tax_status },
  { id: "account_type", label: "Type", value: (row) => row.account_type },
  {
    id: "account_number",
    label: "Account number",
    value: (row) => row.account_number,
  },
  { id: "nickname", label: "Nickname", value: (row) => row.nickname },
];

const EMPTY: readonly AccountSummary[] = [];

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
  const { data, error, isFetching, isDemo } = useLiveQuery(
    "accounts",
    fetchAccounts,
  );
  const view = useTableView(data?.accounts ?? EMPTY, COLUMNS, "tax_status");

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
      error={error}
      isFetching={isFetching}
      hasData={Boolean(data)}
      loadingMessage={
        isDemo ? "Building the demo account list…" : "Fetching your accounts…"
      }
    >
      {data && (
        <>
          <Stack
            direction="row"
            justifyContent="flex-end"
            alignItems="center"
            spacing={1}
            sx={{ mb: 1 }}
          >
            <TableSearch
              value={view.query}
              onChange={view.setQuery}
              label="accounts"
            />
            {/* Exports what is on screen, filtering included. */}
            <CsvButton
              name={["accounts"]}
              demo={data.demo}
              headers={COLUMNS.map((column) => column.label)}
              rows={view.rows.map((account) => [
                account.tax_status,
                account.account_type,
                account.account_number,
                account.nickname,
              ])}
            />
          </Stack>
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <SortableHead columns={COLUMNS} view={view} />
              <TableBody>
                {view.rows.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={COLUMNS.length}>
                      <Typography variant="body2" color="text.secondary">
                        {view.total === 0
                          ? "No Robinhood accounts found."
                          : `No account matches “${view.query}”`}
                      </Typography>
                    </TableCell>
                  </TableRow>
                )}
                {view.rows.map((account, index) => (
                  <TableRow
                    key={account.account_number ?? `row-${String(index)}`}
                    hover
                  >
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
        </>
      )}
    </ReportPage>
  );
}
