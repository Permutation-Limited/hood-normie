/**
 * Covers CSV serialization, which no other test reaches: a quoting mistake here
 * silently corrupts an export rather than failing visibly in the browser.
 *
 * Imports the TypeScript source directly; Node strips the types.
 */
import assert from "node:assert/strict";
import { csvFilename, toCsv } from "../src/csv.ts";

// A field containing a delimiter, a quote, or a newline must survive a round
// trip through a spreadsheet, so it is quoted and its quotes are doubled.
assert.equal(
  toCsv(["a", "b"], [["plain", "has,comma"]]),
  'a,b\r\nplain,"has,comma"',
);
assert.equal(toCsv(["a"], [['say "hi"']]), 'a\r\n"say ""hi"""');
assert.equal(toCsv(["a"], [["two\nlines"]]), 'a\r\n"two\nlines"');

// Missing fields are empty, not the string "null".
assert.equal(toCsv(["a", "b"], [[null, "x"]]), "a,b\r\n,x");

// Rows are separated by CRLF, per RFC 4180.
assert.equal(toCsv(["a"], [["1"], ["2"]]), "a\r\n1\r\n2");

// A value a spreadsheet would execute is neutralized...
assert.equal(toCsv(["a"], [["=SUM(A1:A9)"]]), "a\r\n'=SUM(A1:A9)");
assert.equal(toCsv(["a"], [["@import"]]), "a\r\n'@import");
// ...but a negative amount is data, and must not be mangled into text.
assert.equal(toCsv(["a"], [["-2000.00"]]), "a\r\n-2000.00");
assert.equal(toCsv(["a"], [["-5"]]), "a\r\n-5");

// Demo exports carry the word in the filename, since a CSV has no banner.
const demoName = csvFilename(["holdings", "Roth IRA · 111"], true);
assert.match(demoName, /^hood-normie-holdings-roth-ira-111-demo-\d{4}-\d{2}-\d{2}\.csv$/);
const liveName = csvFilename(["accounts"], false);
assert.match(liveName, /^hood-normie-accounts-\d{4}-\d{2}-\d{2}\.csv$/);
assert.ok(!liveName.includes("demo"));

console.log("csv checks passed");
