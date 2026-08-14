import Button from "@mui/material/Button";
import Tooltip from "@mui/material/Tooltip";
import DownloadIcon from "@mui/icons-material/Download";
import type { CsvRow } from "../csv";
import { csvFilename, downloadCsv, toCsv } from "../csv";
import type { ReactElement } from "react";

/** Downloads one table as CSV. Demo exports are named as such. */
export default function CsvButton({
  name,
  demo,
  headers,
  rows,
}: {
  /** Filename parts, e.g. ["holdings", "Roth IRA · 111"]. */
  name: readonly string[];
  demo: boolean;
  headers: CsvRow;
  rows: readonly CsvRow[];
}): ReactElement {
  return (
    <Tooltip title="Download this table as CSV">
      <Button
        size="small"
        startIcon={<DownloadIcon />}
        onClick={() => {
          downloadCsv(csvFilename(name, demo), toCsv(headers, rows));
        }}
      >
        CSV
      </Button>
    </Tooltip>
  );
}
