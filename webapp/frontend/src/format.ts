/** Display helpers. Input is always a decimal string from the API. */

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const quantity = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 6,
});

export function money(value: string): string {
  return currency.format(Number(value));
}

/** Absolute value, for tables where a separate column carries the direction. */
export function moneyAbs(value: string): string {
  return currency.format(Math.abs(Number(value)));
}

export function shares(value: string): string {
  return quantity.format(Number(value));
}

export function isNegative(value: string): boolean {
  return Number(value) < 0;
}
