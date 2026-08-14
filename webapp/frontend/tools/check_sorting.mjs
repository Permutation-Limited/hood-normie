/**
 * Covers table sorting and filtering. Ordering money by string would put $9,000
 * above $85,000, so the numeric path is worth a test of its own.
 *
 * Imports the TypeScript source directly; Node strips the types.
 */
import assert from "node:assert/strict";
import { compare, filterRows, sortRows } from "../src/sorting.ts";

const columns = [
  { id: "symbol", label: "Symbol", value: (row) => row.symbol },
  { id: "value", label: "Value", numeric: true, value: (row) => Number(row.value) },
  { id: "class", label: "Class", value: (row) => row.assetClass },
];
const rows = [
  { symbol: "VTI", value: "85650.00", assetClass: "stocks" },
  { symbol: "BND", value: "9830.00", assetClass: "bonds" },
  { symbol: "GLD", value: "245.75", assetClass: null },
];

const symbols = (list) => list.map((row) => row.symbol);
const byId = (id) => columns.find((column) => column.id === id);

// Text sorts alphabetically, both ways.
assert.deepEqual(symbols(sortRows(rows, byId("symbol"), "asc")), ["BND", "GLD", "VTI"]);
assert.deepEqual(symbols(sortRows(rows, byId("symbol"), "desc")), ["VTI", "GLD", "BND"]);

// Money sorts by magnitude, not by leading digit.
assert.deepEqual(symbols(sortRows(rows, byId("value"), "asc")), ["GLD", "BND", "VTI"]);
assert.deepEqual(symbols(sortRows(rows, byId("value"), "desc")), ["VTI", "BND", "GLD"]);

// An unavailable value sorts last ascending (GLD has no class), rather than
// sorting as empty text and heading the list.
assert.deepEqual(symbols(sortRows(rows, byId("class"), "asc")), ["BND", "VTI", "GLD"]);

// Sorting never mutates the caller's array.
const original = [...rows];
sortRows(rows, byId("value"), "desc");
assert.deepEqual(rows, original);

// No column selected leaves the given order alone.
assert.deepEqual(symbols(sortRows(rows, undefined, "asc")), ["VTI", "BND", "GLD"]);

// Search matches any column, case-insensitively, and ignores surrounding space.
assert.deepEqual(symbols(filterRows(rows, columns, "vt")), ["VTI"]);
assert.deepEqual(symbols(filterRows(rows, columns, "  BONDS ")), ["BND"]);
assert.deepEqual(symbols(filterRows(rows, columns, "")), ["VTI", "BND", "GLD"]);
assert.deepEqual(symbols(filterRows(rows, columns, "nope")), []);
// A row whose only match is a numeric column still matches.
assert.deepEqual(symbols(filterRows(rows, columns, "245")), ["GLD"]);

// Numbers compare numerically; text compares without case or accent noise.
assert.ok(compare(2, 10) < 0);
assert.equal(compare("abc", "ABC"), 0);
assert.equal(compare(null, null), 0);
assert.ok(compare(null, "a") > 0);
assert.ok(compare("a", null) < 0);

console.log("sorting checks passed");
