/**
 * Message of a field-array level error. Depending on the resolver version it sits on
 * `.root.message` or `.message`.
 */
export function arrayError(error: unknown): string | undefined {
  const e = error as { message?: unknown; root?: { message?: unknown } } | undefined;
  const message = e?.root?.message ?? e?.message;
  return typeof message === "string" ? message : undefined;
}
