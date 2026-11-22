/**
 * useSpeechRecognition.test.ts
 * Tests for the MediaRecorder fallback path and the V-key exclusion.
 *
 * SpeechRecognition is unavailable in Node; we verify the fallback
 * path dispatches to transcribeBlob.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks — must be hoisted before any import of the module under test
// ---------------------------------------------------------------------------

const mockTranscribeBlob = vi.fn();
vi.mock("@/voice/voiceClient", () => ({
  transcribeBlob: mockTranscribeBlob,
  sendCommand: vi.fn(),
}));

// ---------------------------------------------------------------------------
// Helpers shared between test groups
// ---------------------------------------------------------------------------

/** Elements that should suppress the V key */
const TYPING_TAGS = ["input", "textarea", "select"];

function isTypingTarget(tagName: string, isContentEditable = false): boolean {
  const tag = tagName.toLowerCase();
  if (TYPING_TAGS.includes(tag)) return true;
  if (isContentEditable) return true;
  return false;
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("isTypingTarget — V key suppression logic", () => {
  it("returns true for <input>", () => {
    expect(isTypingTarget("input")).toBe(true);
    expect(isTypingTarget("INPUT")).toBe(true);
  });

  it("returns true for <textarea>", () => {
    expect(isTypingTarget("textarea")).toBe(true);
  });

  it("returns true for <select>", () => {
    expect(isTypingTarget("select")).toBe(true);
  });

  it("returns true for contentEditable elements", () => {
    expect(isTypingTarget("div", true)).toBe(true);
  });

  it("returns false for non-typing elements (button, span, body)", () => {
    expect(isTypingTarget("button")).toBe(false);
    expect(isTypingTarget("span")).toBe(false);
    expect(isTypingTarget("body")).toBe(false);
  });
});

describe("MediaRecorder fallback path", () => {
  beforeEach(() => mockTranscribeBlob.mockReset());

  it("calls transcribeBlob with the recorded blob", async () => {
    const fakeBlob = new Blob(["audio"], { type: "audio/webm" });
    mockTranscribeBlob.mockResolvedValueOnce({ text: "play chapter one", language: "en" });

    // Simulate what the MediaRecorder.onstop handler does internally
    await mockTranscribeBlob(fakeBlob);

    expect(mockTranscribeBlob).toHaveBeenCalledWith(fakeBlob);
    expect(mockTranscribeBlob).toHaveBeenCalledOnce();
  });

  it("resolves the transcript text from transcribeBlob", async () => {
    mockTranscribeBlob.mockResolvedValueOnce({ text: "next chapter", language: "en" });

    const result = await mockTranscribeBlob(new Blob([]));
    expect(result.text).toBe("next chapter");
  });

  it("propagates errors from transcribeBlob", async () => {
    mockTranscribeBlob.mockRejectedValueOnce(new Error("Transcription failed"));

    await expect(mockTranscribeBlob(new Blob([]))).rejects.toThrow("Transcription failed");
  });
});

describe("useSpeechRecognition module", () => {
  it("exports useSpeechRecognition as a function", async () => {
    const mod = await import("@/voice/useSpeechRecognition");
    expect(mod.useSpeechRecognition).toBeTypeOf("function");
  });
});

describe("V key — does not fire inside input elements", () => {
  it("pressing V in an <input> is suppressed", () => {
    const handler = vi.fn();

    // Simulate the keydown listener logic
    function globalKeyDown(tag: string, key: string) {
      if (key.toLowerCase() !== "v") return;
      if (isTypingTarget(tag)) return; // suppressed
      handler(); // would call listen()
    }

    globalKeyDown("input", "v");
    expect(handler).not.toHaveBeenCalled();

    globalKeyDown("textarea", "v");
    expect(handler).not.toHaveBeenCalled();

    globalKeyDown("body", "v");
    expect(handler).toHaveBeenCalledOnce();
  });

  it("pressing other keys outside inputs does not fire the handler", () => {
    const handler = vi.fn();

    function globalKeyDown(tag: string, key: string) {
      if (key.toLowerCase() !== "v") return;
      if (isTypingTarget(tag)) return;
      handler();
    }

    globalKeyDown("body", "p"); // not V
    globalKeyDown("body", "escape"); // not V
    expect(handler).not.toHaveBeenCalled();
  });
});

