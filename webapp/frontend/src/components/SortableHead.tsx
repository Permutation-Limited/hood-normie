import TableCell from "@mui/material/TableCell";
import TableHead from "@mui/material/TableHead";
import TableRow from "@mui/material/TableRow";
import TableSortLabel from "@mui/material/TableSortLabel";
import type { Column } from "../sorting";
import type { TableView } from "../useTableView";
import type { ReactElement } from "react";

/** A header row whose cells sort the table. */
export default function SortableHead<T>({
  columns,
  view,
}: {
  columns: readonly Column<T>[];
  view: TableView<T>;
}): ReactElement {
  return (
    <TableHead>
      <TableRow>
        {columns.map((column) => (
          <TableCell
            key={column.id}
            align={column.numeric ? "right" : "left"}
            sortDirection={view.orderBy === column.id ? view.order : false}
          >
            <TableSortLabel
              active={view.orderBy === column.id}
              direction={view.orderBy === column.id ? view.order : "asc"}
              onClick={() => {
                view.toggleSort(column.id);
              }}
            >
              {column.label}
            </TableSortLabel>
          </TableCell>
        ))}
      </TableRow>
    </TableHead>
  );
}
