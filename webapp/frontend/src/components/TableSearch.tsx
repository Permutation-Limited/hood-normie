import IconButton from "@mui/material/IconButton";
import InputAdornment from "@mui/material/InputAdornment";
import TextField from "@mui/material/TextField";
import ClearIcon from "@mui/icons-material/Clear";
import SearchIcon from "@mui/icons-material/Search";
import type { ReactElement } from "react";

/** Filters one table. Narrow by design: it sits in a table's header row. */
export default function TableSearch({
  value,
  onChange,
  label,
}: {
  value: string;
  onChange: (value: string) => void;
  /** What the box searches, e.g. "symbols". */
  label: string;
}): ReactElement {
  return (
    <TextField
      size="small"
      variant="outlined"
      value={value}
      placeholder={`Search ${label}`}
      aria-label={`Search ${label}`}
      onChange={(event) => {
        onChange(event.target.value);
      }}
      sx={{ width: { xs: 140, sm: 200 } }}
      slotProps={{
        input: {
          startAdornment: (
            <InputAdornment position="start">
              <SearchIcon fontSize="small" color="disabled" />
            </InputAdornment>
          ),
          endAdornment: value ? (
            <InputAdornment position="end">
              <IconButton
                size="small"
                aria-label="Clear search"
                onClick={() => {
                  onChange("");
                }}
              >
                <ClearIcon fontSize="small" />
              </IconButton>
            </InputAdornment>
          ) : null,
        },
      }}
    />
  );
}
