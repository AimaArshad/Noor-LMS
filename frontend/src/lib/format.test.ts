import { describe, expect, it } from "vitest";

import { formatPoints, toIsoFromLocalInput } from "@/lib/format";

describe("toIsoFromLocalInput", () => {
  it("returns undefined for empty or invalid input", () => {
    expect(toIsoFromLocalInput("")).toBeUndefined();
    expect(toIsoFromLocalInput("not a date")).toBeUndefined();
  });

  it("converts a datetime-local value to a UTC ISO string", () => {
    const value = "2030-01-01T10:00";
    expect(toIsoFromLocalInput(value)).toBe(new Date(value).toISOString());
    expect(toIsoFromLocalInput(value)).toMatch(/Z$/);
  });
});

describe("formatPoints", () => {
  it("shows whole numbers without decimals and others with two", () => {
    expect(formatPoints(45)).toBe("45");
    expect(formatPoints(8.5)).toBe("8.50");
  });
});
