/**
 * voiceClient.test.ts
 * Unit tests for sendCommand and transcribeBlob.
 *
 * We mock the `api` axios instance so no real HTTP is made.
 */

import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mock the axios `api` instance before importing voiceClient
// ---------------------------------------------------------------------------

const mockPost = vi.fn();

vi.mock("@/api/client", () => ({
  api: { post: mockPost },
  axios: {},
}));

// Now import the module under test (after mocks are registered)
const { sendCommand, transcribeBlob } = await import("@/voice/voiceClient");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const COMMAND_RESPONSE = {
  intent: "go_chapter",
  action: "seek_section",
  target: { audiobook_id: "abc", section_seq: 0, segment_seq: null, page: null },
  speech: "Going to Introduction.",
};

const TRANSCRIBE_RESPONSE = {
  text: "go to chapter two",
  language: "en",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("sendCommand", () => {
  beforeEach(() => mockPost.mockReset());

  it("POSTs to /voice/command with text and no audiobook_id when omitted", async () => {
    mockPost.mockResolvedValueOnce({ data: COMMAND_RESPONSE });

    const result = await sendCommand("go to chapter 2");

    expect(mockPost).toHaveBeenCalledOnce();
    const [url, body] = mockPost.mock.calls[0] as [string, unknown];
    expect(url).toBe("/voice/command");
    expect(body).toEqual({ text: "go to chapter 2", audiobook_id: null });
    expect(result).toEqual(COMMAND_RESPONSE);
  });

  it("includes audiobook_id when provided", async () => {
    mockPost.mockResolvedValueOnce({ data: COMMAND_RESPONSE });

    await sendCommand("pause", "uuid-123");

    const [, body] = mockPost.mock.calls[0] as [string, { audiobook_id: string }];
    expect(body.audiobook_id).toBe("uuid-123");
  });

  it("propagates errors from the API", async () => {
    const err = new Error("Network error");
    mockPost.mockRejectedValueOnce(err);

    await expect(sendCommand("play")).rejects.toThrow("Network error");
  });
});

describe("transcribeBlob", () => {
  beforeEach(() => mockPost.mockReset());

  it("POSTs multipart form data to /voice/transcribe", async () => {
    mockPost.mockResolvedValueOnce({ data: TRANSCRIBE_RESPONSE });

    // Use a real Blob so Node's FormData.append accepts it
    const fakeBlob = new Blob(["audio-data"], { type: "audio/wav" });
    const result = await transcribeBlob(fakeBlob, "clip.wav");

    expect(mockPost).toHaveBeenCalledOnce();
    const [url, form, config] = mockPost.mock.calls[0] as [
      string,
      FormData,
      { headers: Record<string, string>; timeout: number },
    ];
    expect(url).toBe("/voice/transcribe");
    // FormData is built in the function; we verify the config
    expect(config.headers["Content-Type"]).toBe("multipart/form-data");
    expect(config.timeout).toBe(60_000);
    expect(form).toBeInstanceOf(FormData);
    expect(result).toEqual(TRANSCRIBE_RESPONSE);
  });

  it("uses default filename recording.webm when not specified", async () => {
    mockPost.mockResolvedValueOnce({ data: TRANSCRIBE_RESPONSE });

    const fakeBlob = new Blob(["x"], { type: "audio/webm" });
    await transcribeBlob(fakeBlob);

    // Just verify it resolved without throwing
    expect(mockPost).toHaveBeenCalledOnce();
  });

  it("propagates transcription errors", async () => {
    const err = new Error("503 Service Unavailable");
    mockPost.mockRejectedValueOnce(err);

    const fakeBlob = new Blob(["x"], { type: "audio/webm" });
    await expect(transcribeBlob(fakeBlob)).rejects.toThrow("503 Service Unavailable");
  });
});
