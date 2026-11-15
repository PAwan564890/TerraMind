/** Display only: never replace API numbers or validated claim strings. */
export function formatMetric(
  value: number | null | undefined,
  unit: "°C" | "mm",
) {
  if (value == null || !Number.isFinite(value)) return "Unavailable";
  const digits = unit === "°C" ? 2 : 1;
  return value.toLocaleString(undefined, {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}
