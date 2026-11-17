import { AxiosError, type AxiosResponse } from "axios";
import { describe, expect, it } from "vitest";

import { getErrorMessage, getStatus } from "@/api/errors";

function httpError(status: number, data: unknown): AxiosError {
  const response = { status, data, statusText: "", headers: {}, config: {} } as unknown as AxiosResponse;
  return new AxiosError("failed", "ERR_BAD_REQUEST", undefined, undefined, response);
}

describe("getStatus", () => {
  it("reads the HTTP status of axios errors only", () => {
    expect(getStatus(httpError(409, {}))).toBe(409);
    expect(getStatus(new AxiosError("Network Error"))).toBeUndefined();
    expect(getStatus(new Error("boom"))).toBeUndefined();
  });
});

describe("getErrorMessage", () => {
  it("uses a string `detail` from the API", () => {
    expect(getErrorMessage(httpError(409, { detail: "Email already registered" }))).toBe(
      "Email already registered",
    );
  });

  it("joins 422 validation issues, dropping the `body` prefix", () => {
    const error = httpError(422, { detail: [{ loc: ["body", "email"], msg: "invalid email" }] });
    expect(getErrorMessage(error)).toBe("email: invalid email");
  });

  it("explains network failures and rate limits", () => {
    expect(getErrorMessage(new AxiosError("Network Error", "ERR_NETWORK"))).toMatch(
      /Cannot reach the server/,
    );
    expect(getErrorMessage(httpError(429, {}))).toMatch(/Too many requests/);
  });

  it("handles plain errors and unknown values", () => {
    expect(getErrorMessage(new Error("boom"))).toBe("boom");
    expect(getErrorMessage("weird", "fallback text")).toBe("fallback text");
  });
});
