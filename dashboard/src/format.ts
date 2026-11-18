const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
});

export function money(amount: number | string): string {
  return currency.format(Number(amount));
}

export function dateTime(value: string): string {
  return new Date(value).toLocaleString("en-US", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

export function humanize(value: string): string {
  return value.replaceAll("_", " ");
}
