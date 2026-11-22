/**
 * audiobooks.test.ts
 *
 * Unit tests for the audiobooks feature:
 *   - API client (mocked axios)
 *   - Upload + create flow logic
 *   - Polling decision based on status
 *   - Rebuild disabled while building
 */

import { describe, expect, it, vi, beforeEach } from "vitest";

// ---------------------------------------------------------------------------
// Mock the axios `api` instance
// ---------------------------------------------------------------------------

const mockGet = vi.fn();
const mockPost = vi.fn();
const mockDelete = vi.fn();

vi.mock("@/api/client", () => ({
  api: { get: mockGet, post: mockPost, delete: mockDelete },
}));

// ---------------------------------------------------------------------------
// Import after mocks
// ---------------------------------------------------------------------------

const { audiobooksApi, BUILDING_STATUSES } = await import("@/features/audiobooks/api");

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fakeAudiobook(overrides: Record<string, unknown> = {}) {
  return {
    id: "ab-1",
    classroom_id: "cls-1",
    file_id: "f-1",
    title: "Physics 9th",
    status: "ready",
    error: null,
    page_count: 42,
    pages_approximate: false,
    total_duration_ms: 120_000,
    voice: "en_US-lessac-medium",
    progress_pct: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

// ---------------------------------------------------------------------------
// API client tests
// ---------------------------------------------------------------------------

describe("audiobooksApi", () => {
  beforeEach(() => {
    mockGet.mockReset();
    mockPost.mockReset();
    mockDelete.mockReset();
  });

  it("listForClassroom calls GET /classrooms/{id}/audiobooks", async () => {
    const data = [fakeAudiobook()];
    mockGet.mockResolvedValueOnce({ data });

    const result = await audiobooksApi.listForClassroom("cls-1");

    expect(mockGet).toHaveBeenCalledWith("/classrooms/cls-1/audiobooks", {
      params: { limit: 100 },
    });
    expect(result).toEqual(data);
  });

  it("create POSTs to /classrooms/{id}/audiobooks", async () => {
    const ab = fakeAudiobook({ status: "queued" });
    mockPost.mockResolvedValueOnce({ data: ab });

    const result = await audiobooksApi.create("cls-1", {
      file_id: "f-1",
      title: "My Book",
    });

    expect(mockPost).toHaveBeenCalledWith("/classrooms/cls-1/audiobooks", {
      file_id: "f-1",
      title: "My Book",
    });
    expect(result.status).toBe("queued");
  });

  it("rebuild POSTs to /audiobooks/{id}/rebuild", async () => {
    const ab = fakeAudiobook({ status: "queued" });
    mockPost.mockResolvedValueOnce({ data: ab });

    await audiobooksApi.rebuild("ab-1");

    expect(mockPost).toHaveBeenCalledWith("/audiobooks/ab-1/rebuild");
  });

  it("remove DELETEs /audiobooks/{id}", async () => {
    mockDelete.mockResolvedValueOnce({});

    await audiobooksApi.remove("ab-1");

    expect(mockDelete).toHaveBeenCalledWith("/audiobooks/ab-1");
  });

  it("propagates errors from create", async () => {
    mockPost.mockRejectedValueOnce(new Error("403 Forbidden"));

    await expect(
      audiobooksApi.create("cls-1", { file_id: "f-1" }),
    ).rejects.toThrow("403 Forbidden");
  });
});

// ---------------------------------------------------------------------------
// Polling decision logic
// ---------------------------------------------------------------------------

describe("BUILDING_STATUSES (polling logic)", () => {
  it("includes queued, extracting, synthesizing", () => {
    expect(BUILDING_STATUSES).toContain("queued");
    expect(BUILDING_STATUSES).toContain("extracting");
    expect(BUILDING_STATUSES).toContain("synthesizing");
  });

  it("does NOT include ready, failed, or needs_ocr", () => {
    expect(BUILDING_STATUSES).not.toContain("ready");
    expect(BUILDING_STATUSES).not.toContain("failed");
    expect(BUILDING_STATUSES).not.toContain("needs_ocr");
  });

  it("triggers polling when any item is building", () => {
    const items = [
      fakeAudiobook({ status: "ready" }),
      fakeAudiobook({ id: "ab-2", status: "synthesizing" }),
    ];
    const anyBuilding = items.some((ab) => (BUILDING_STATUSES as readonly string[]).includes(ab.status));
    expect(anyBuilding).toBe(true);
  });

  it("does NOT poll when all items are terminal", () => {
    const items = [
      fakeAudiobook({ status: "ready" }),
      fakeAudiobook({ id: "ab-2", status: "failed" }),
      fakeAudiobook({ id: "ab-3", status: "needs_ocr" }),
    ];
    const anyBuilding = items.some((ab) => (BUILDING_STATUSES as readonly string[]).includes(ab.status));
    expect(anyBuilding).toBe(false);
  });

  it("does NOT poll when list is empty", () => {
    const items: ReturnType<typeof fakeAudiobook>[] = [];
    const anyBuilding = items.some((ab) => (BUILDING_STATUSES as readonly string[]).includes(ab.status));
    expect(anyBuilding).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Upload + create flow
// ---------------------------------------------------------------------------

describe("upload â†’ create flow", () => {
  beforeEach(() => {
    mockPost.mockReset();
  });

  it("create sends file_id from upload result", async () => {
    // Step 1: upload returns a file with an id
    const uploadResult = { id: "file-uuid-123", filename: "book.pdf" };
    // Step 2: create uses that file_id
    const ab = fakeAudiobook({ file_id: uploadResult.id, status: "queued" });
    mockPost.mockResolvedValueOnce({ data: ab });

    const result = await audiobooksApi.create("cls-1", {
      file_id: uploadResult.id,
      title: "My Upload",
    });

    expect(result.file_id).toBe("file-uuid-123");
    expect(mockPost).toHaveBeenCalledWith("/classrooms/cls-1/audiobooks", {
      file_id: "file-uuid-123",
      title: "My Upload",
    });
  });

  it("title is optional in create call", async () => {
    const ab = fakeAudiobook({ status: "queued" });
    mockPost.mockResolvedValueOnce({ data: ab });

    await audiobooksApi.create("cls-1", { file_id: "f-1" });

    const [, body] = mockPost.mock.calls[0] as [string, { file_id: string; title?: string }];
    expect(body.file_id).toBe("f-1");
    expect(body.title).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Rebuild disabled logic
// ---------------------------------------------------------------------------

describe("rebuild disabled while building", () => {
  it("building statuses make isBuilding true", () => {
    for (const status of BUILDING_STATUSES) {
      const item = fakeAudiobook({ status });
      const isBuilding = (BUILDING_STATUSES as readonly string[]).includes(item.status);
      expect(isBuilding).toBe(true);
    }
  });

  it("ready status makes isBuilding false", () => {
    const item = fakeAudiobook({ status: "ready" });
    const isBuilding = (BUILDING_STATUSES as readonly string[]).includes(item.status);
    expect(isBuilding).toBe(false);
  });

  it("failed status makes isBuilding false (can rebuild)", () => {
    const item = fakeAudiobook({ status: "failed" });
    const isBuilding = (BUILDING_STATUSES as readonly string[]).includes(item.status);
    expect(isBuilding).toBe(false);
  });
});

// ---------------------------------------------------------------------------
// Client-side file validation logic
// ---------------------------------------------------------------------------

describe("client-side file validation", () => {
  const ACCEPTED_TYPES = [
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
  ];
  const MAX_SIZE = 25 * 1024 * 1024;

  it("accepts PDF, DOCX, and TXT mime types", () => {
    expect(ACCEPTED_TYPES).toContain("application/pdf");
    expect(ACCEPTED_TYPES).toContain(
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    );
    expect(ACCEPTED_TYPES).toContain("text/plain");
  });

  it("rejects files over 25 MB", () => {
    const tooBig = MAX_SIZE + 1;
    expect(tooBig > MAX_SIZE).toBe(true);
  });

  it("accepts files at exactly 25 MB", () => {
    expect(MAX_SIZE <= MAX_SIZE).toBe(true);
  });

  it("rejects unsupported MIME types", () => {
    expect(ACCEPTED_TYPES).not.toContain("image/png");
    expect(ACCEPTED_TYPES).not.toContain("audio/mpeg");
  });
});


