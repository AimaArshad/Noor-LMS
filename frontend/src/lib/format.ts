const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** "Oct 11, 2026, 3:30 PM" in the user's locale and time zone. */
export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** `datetime-local` input value -> UTC ISO string (the API needs timezone-aware datetimes). */
export function toIsoFromLocalInput(value: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/** 45 -> "45", 8.5 -> "8.50". */
export function formatPoints(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}
