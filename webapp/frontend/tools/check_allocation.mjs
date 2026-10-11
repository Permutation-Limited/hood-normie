/**
 * Covers the allocation donuts' data: exact sums, stable class colors, the
 * negatives a donut cannot draw, and folding a long tail into "other".
 *
 * Imports the TypeScript source directly; Node strips the types.
 */
import assert from "node:assert/strict";
import {
  MAX_SLICES,
  addDecimal,
  classBySymbol,
  classSlots,
  currentByClass,
  targetByClass,
} from "../src/allocation.ts";

// Exact at any scale, with no float drift.
assert.equal(addDecimal("0.1", "0.2"), "0.3");
assert.equal(addDecimal("1000.50", "-2000"), "-999.50");
assert.equal(addDecimal("0", "12.3456"), "12.3456");
assert.equal(addDecimal("-0.05", "0.05"), "0.00");

const position = (symbol, assetClass, value) => ({
  symbol,
  asset_class: assetClass,
  quantity: "1",
  price: value,
  market_value: value,
});
const recommendations = ["stocks", "bonds", "cash"].map((name) => ({
  asset_class: name,
  action: "HOLD",
  amount: "0",
  current_value: "0",
  target_value: name === "cash" ? "-2000" : "500",
  ignored: false,
}));
const accounts = [
  {
    label: "A",
    kind: "robinhood",
    cash: "-300",
    total_value: "0",
    positions: [position("VTI", "stocks", "700.10"), position("BND", "bonds", "100")],
  },
  {
    label: "B",
    kind: "external",
    cash: "100",
    total_value: "0",
    positions: [position("VXUS", "stocks", "0.25"), position("ODD", null, "50")],
  },
];

// Classes keep the plan's order of colors, cash excluded, unclassified last.
const slots = classSlots(recommendations);
assert.deepEqual([...slots], [["stocks", 0], ["bonds", 1], ["unclassified", 2]]);

// Current sums across accounts, largest first; net margin cash is set aside.
const current = currentByClass(accounts, slots);
assert.deepEqual(
  current.slices.map((slice) => [slice.key, slice.amount, slice.slot, slice.drillable]),
  [
    ["stocks", "700.35", 0, true],
    ["bonds", "100", 1, true],
    ["unclassified", "50", 2, true],
  ],
);
assert.deepEqual(current.excluded, [{ label: "cash", amount: "-200" }]);

// One account alone: its positive cash is a neutral, unopenable slice, and
// bonds keeps its color even though stocks is the only other class.
const single = currentByClass([accounts[1]], slots);
assert.deepEqual(
  single.slices.map((slice) => [slice.key, slice.slot, slice.drillable]),
  [
    ["cash", null, false],
    ["unclassified", 2, true],
    ["stocks", 0, true],
  ],
);

// Targets come from the plan; a negative cash target is set aside too.
const target = targetByClass(recommendations, slots);
assert.deepEqual(target.slices.map((slice) => slice.key), ["stocks", "bonds"]);
assert.deepEqual(target.excluded, [{ label: "cash", amount: "-2000" }]);

// Opening a class lists its symbols across accounts.
assert.deepEqual(
  classBySymbol(accounts, "stocks").slices.map((slice) => [slice.key, slice.slot]),
  [["VTI", 0], ["VXUS", 1]],
);
assert.deepEqual(
  classBySymbol(accounts, "unclassified").slices.map((slice) => slice.key),
  ["ODD"],
);

// Past the slice limit the smallest fold into one neutral "other" slice.
const many = [
  {
    label: "M",
    kind: "robinhood",
    cash: "0",
    total_value: "0",
    positions: Array.from({ length: 10 }, (_, index) =>
      position(`S${index}`, "stocks", String(100 - index)),
    ),
  },
];
const folded = classBySymbol(many, "stocks").slices;
assert.equal(folded.length, MAX_SLICES);
assert.deepEqual(folded.at(-1), {
  key: "other",
  label: "3 others",
  amount: "276",
  value: 276,
  slot: null,
  drillable: false,
});

console.log("allocation: ok");
