/** Format integer pence as GBP, e.g. 3200 -> "£32.00". */
export function formatGBP(pence: number): string {
  if (!Number.isFinite(pence)) return "—";
  const sign = pence < 0 ? "-" : "";
  return `${sign}£${(Math.abs(pence) / 100).toFixed(2)}`;
}
