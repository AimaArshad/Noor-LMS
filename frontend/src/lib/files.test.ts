import { describe, expect, it } from "vitest";

import { extensionOf, formatBytes, validateFile } from "@/lib/files";

describe("validateFile", () => {
  it("accepts allowed types in any letter case", () => {
    expect(validateFile(new File(["x"], "notes.pdf"))).toBeNull();
    expect(validateFile(new File(["x"], "PHOTO.JPG"))).toBeNull();
  });

  it("rejects disallowed extensions", () => {
    expect(validateFile(new File(["x"], "run.exe"))).toMatch(/not allowed/);
    expect(validateFile(new File(["x"], "page.html"))).toMatch(/not allowed/);
    expect(validateFile(new File(["x"], "README"))).toMatch(/not allowed/);
  });

  it("rejects empty and oversized files", () => {
    expect(validateFile(new File([], "empty.txt"))).toMatch(/empty/);
    const big = new File(["x"], "big.txt");
    Object.defineProperty(big, "size", { value: 26 * 1024 * 1024 });
    expect(validateFile(big)).toMatch(/larger than 25 MB/);
  });
});

describe("helpers", () => {
  it("extensionOf", () => {
    expect(extensionOf("a.TAR.GZ")).toBe(".gz");
    expect(extensionOf("noext")).toBe("");
  });

  it("formatBytes", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});
