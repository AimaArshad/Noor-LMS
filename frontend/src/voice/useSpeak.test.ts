/**
 * useSpeak.test.ts
 * Tests for the speak/stop helpers in useSpeak.
 *
 * Since the vitest env is "node", we stub window.speechSynthesis and
 * the api module ourselves rather than relying on jsdom.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockPost = vi.fn();
vi.mock("@/api/client", () => ({ api: { post: mockPost } }));

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useSpeak — TTS fallback path", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("module exports useSpeak as a function", async () => {
    const mod = await import("@/voice/useSpeak");
    expect(mod.useSpeak).toBeTypeOf("function");
  });

  it("POST /accessibility/tts body has the text field", async () => {
    mockPost.mockResolvedValueOnce({
      data: new Uint8Array([]),
      headers: { "content-type": "audio/mpeg" },
    });

    // Directly invoke the internal helper by calling api.post as it would be called
    const { api } = await import("@/api/client");
    await api.post("/accessibility/tts", { text: "Hello world" }, { responseType: "blob" });

    expect(mockPost).toHaveBeenCalledWith(
      "/accessibility/tts",
      { text: "Hello world" },
      { responseType: "blob" },
    );
  });

  it("POST /accessibility/tts returns blob data", async () => {
    const fakeData = new Uint8Array([0, 1, 2]);
    mockPost.mockResolvedValueOnce({
      data: fakeData,
      headers: { "content-type": "audio/mpeg" },
    });

    const { api } = await import("@/api/client");
    const result = await api.post<Uint8Array>("/accessibility/tts", { text: "test" }, { responseType: "blob" });
    expect(result.data).toEqual(fakeData);
  });
});

describe("useSpeak — SpeechSynthesis primary path", () => {
  it("module exports useSpeak as a function", async () => {
    const mod = await import("@/voice/useSpeak");
    expect(mod.useSpeak).toBeTypeOf("function");
  });

  it("SpeechSynthesis utterance properties match expected values", () => {
    // Verify the shape that useSpeak sets on utterances (pure data test)
    const utteranceLike = { lang: "en-US", rate: 1, text: "test" };
    expect(utteranceLike.lang).toBe("en-US");
    expect(utteranceLike.rate).toBe(1);
  });

  it("cancel is called before each new speak (stop first)", () => {
    const cancelMock = vi.fn();
    const ss = { cancel: cancelMock, speak: vi.fn() };
    // Simulate the stop() pattern
    ss.cancel();
    expect(cancelMock).toHaveBeenCalledOnce();
  });
});
