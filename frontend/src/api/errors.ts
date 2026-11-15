import axios from "axios";

/** HTTP status of a failed request, or `undefined` for network errors / non-HTTP errors. */
export function getStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

interface ValidationIssue {
  loc?: unknown[];
  msg?: string;
}

/** Turn any error (FastAPI `detail` string, 422 issue list, network failure) into UI text. */
export function getErrorMessage(
  error: unknown,
  fallback = "Something went wrong. Please try again.",
): string {
  if (axios.isAxiosError(error)) {
    if (!error.response) return "Cannot reach the server. Check your connection.";
    if (error.response.status === 429) return "Too many requests. Please wait a moment and retry.";

    const detail = (error.response.data as { detail?: unknown } | undefined)?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      const messages = (detail as ValidationIssue[])
        .map((issue) => {
          const field = issue.loc?.slice(1).join(".");
          return field ? `${field}: ${issue.msg ?? "invalid"}` : (issue.msg ?? "invalid");
        })
        .filter(Boolean);
      if (messages.length) return messages.join("; ");
    }
    return fallback;
  }
  return error instanceof Error ? error.message : fallback;
}
