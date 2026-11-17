import axios from "axios";

/** HTTP status of a failed request, or `undefined` for network errors / non-HTTP errors. */
export function getStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

interface ValidationDetail {
  field?: string | null;
  message?: string;
}

/** The API's error envelope: `{ error: { code, message, details } }`. */
interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
  detail?: unknown; // legacy shape, kept as a fallback
}

/** Stable machine-readable error code (`not_found`, `validation_error`, ...), if the API sent one. */
export function getErrorCode(error: unknown): string | undefined {
  if (!axios.isAxiosError(error)) return undefined;
  return (error.response?.data as ApiErrorBody | undefined)?.error?.code;
}

/** Turn any error (API envelope, network failure, plain Error) into UI text. */
export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Cannot reach the server. Check your connection.";

    const body = error.response.data as ApiErrorBody | undefined;
    const api = body?.error;

    if (error.response.status === 429) {
      const wait = (api?.details as { retry_after_seconds?: number | null } | null | undefined)
        ?.retry_after_seconds;
      return wait
        ? `Too many requests. Please try again in ${wait} seconds.`
        : "Too many requests. Please wait a moment and retry.";
    }

    if (api) {
      if (api.code === "validation_error" && Array.isArray(api.details)) {
        const messages = (api.details as ValidationDetail[]).map((issue) =>
          issue.field ? `${issue.field}: ${issue.message ?? "invalid"}` : (issue.message ?? "invalid"),
        );
        if (messages.length) return messages.join("; ");
      }
      if (api.message) return api.message;
    }
    if (typeof body?.detail === "string") return body.detail;
    return fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
