import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorCode, getErrorMessage, getStatus } from "@/api/errors";

function httpError(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: "", headers: {}, config: {} } as unknown as AxiosResponse;
  return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

const envelope = (code: string, message: string, details: unknown = null) => ({
  error: { code, message, details },
});

describe("getStatus / getErrorCode", () => {
  it("reads the HTTP status of axios errors only", () => {
    expect(getStatus(httpError(409, {}))).toBe(409);
    expect(getStatus(new AxiosError("Network Error"))).toBeUndefined();
    expect(getStatus(new Error("boom"))).toBeUndefined();
  });

  it("reads the machine-readable code", () => {
    expect(getErrorCode(httpError(404, envelope("not_found", "Classroom not found")))).toBe(
      "not_found",
    );
    expect(getErrorCode(new Error("boom"))).toBeUndefined();
  });
});

describe("getErrorMessage", () => {
  it("uses the message of the error envelope", () => {
    const error = httpError(409, envelope("conflict", "Email already registered"));
    expect(getErrorMessage(error)).toBe("Email already registered");
  });

  it("joins validation issues as `field: message`", () => {
    const error = httpError(
      422,
      envelope("validation_error", "Request validation failed", [
        { in: "body", field: "email", message: "invalid email", type: "value_error" },
        { in: "body", field: null, message: "Provide an answer", type: "value_error" },
      ]),
    );
    expect(getErrorMessage(error)).toBe("email: invalid email; Provide an answer");
  });

  it("tells the user how long to wait after a rate limit", () => {
    const limited = httpError(
      429,
      envelope("rate_limited", "Too many requests.", {
        limit: "10 per 1 minute",
        retry_after_seconds: 42,
      }),
    );
    expect(getErrorMessage(limited)).toMatch(/42 seconds/);
    expect(getErrorMessage(httpError(429, {}))).toMatch(/Too many requests/);
  });

  it("explains network failures and still understands the legacy shape", () => {
    expect(getErrorMessage(new AxiosError("Network Error", "ERR_NETWORK"))).toMatch(
      /Cannot reach the server/,
    );
    expect(getErrorMessage(httpError(400, { detail: "old style" }))).toBe("old style");
  });

  it("handles plain errors and unknown values", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
    expect(getErrorMessage("weird", "fallback text")).toBe("fallback text");
  });
});
