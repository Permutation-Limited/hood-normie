/**
 * CSV export.
 *
 * Exported money and quantities are the API's exact decimal strings, not the
 * formatted display text: a spreadsheet should receive `1000.50`, not
 * `$1,000.50`, so it can total a column without parsing currency.
 */

export type CsvRow = readonly (string | null)[];

/** A field a spreadsheet would evaluate rather than display. */
const FORMULA = /^[=+\-@\t\r]/;
const PLAIN_NUMBER = /^-?\d+(\.\d+)?$/;
const NEEDS_QUOTES = /[",\r\n]/;

export function toCsv(headers: CsvRow, rows: readonly CsvRow[]): string {
  return [headers, ...rows]
    .map((row) => row.map(field).join(","))
    .join("\r\n");
}

function field(value: string | null): string {
  const text = value ?? "";
  // Negative amounts are data, not formulas; anything else a spreadsheet would
  // execute gets a leading quote so it opens as the text it is.
  const safe =
    FORMULA.test(text) && !PLAIN_NUMBER.test(text) ? `'${text}` : text;
  return NEEDS_QUOTES.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe;
}

/**
 * Name a download, marking demo exports.
 *
 * A CSV outlives the page that produced it and carries no banner, so invented
 * numbers must say so in the only place left: the filename.
 */
export function csvFilename(parts: readonly string[], demo: boolean): string {
  const stamp = new Date().toISOString().slice(0, 10);
  const slug = [...parts, ...(demo ? ["demo"] : []), stamp]
    .map((part) =>
      part
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, ""),
    )
    .filter(Boolean)
    .join("-");
  return `hood-normie-${slug}.csv`;
}

export function downloadCsv(filename: string, content: string): void {
  // A BOM, so Excel reads the file as UTF-8 rather than the local codepage.
  const blob = new Blob([`﻿${content}`], {
    type: "text/csv;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
