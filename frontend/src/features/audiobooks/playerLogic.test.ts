import { describe, expect, it } from "vitest";

import type { SectionNode, SegmentInfo } from "./playerApi";
import {
  SEEK_MS,
  adjacentChapterSeq,
  buildOutline,
  buildTimeline,
  commandToAction,
  locate,
  segmentForPage,
  wantsAudiobook,
} from "./playerLogic";

const seg = (seq: number, dur: number | null = 30_000, label = String(seq + 1)): SegmentInfo => ({
  seq,
  section_id: null,
  page_label: label,
  duration_ms: dur,
  status: "ready",
});

const sec = (o: Partial<SectionNode> & { id: string; seq: number; level: number }): SectionNode => ({
  parent_id: null,
  number: null,
  title: `Section ${o.seq}`,
  start_page: 1,
  end_page: null,
  first_segment_seq: null,
  last_segment_seq: null,
  ...o,
});

describe("timeline and seeking across segments", () => {
  const tl = buildTimeline([seg(0), seg(1), seg(2, 15_000)]);

  it("lays segments end to end", () => {
    expect(tl.offsets).toEqual([0, 30_000, 60_000]);
    expect(tl.total).toBe(75_000);
  });

  it("locates a global position", () => {
    expect(locate(tl, 0)).toEqual({ index: 0, offsetMs: 0 });
    expect(locate(tl, 30_000)).toEqual({ index: 1, offsetMs: 0 });
    expect(locate(tl, 74_000)).toEqual({ index: 2, offsetMs: 14_000 });
  });

  it("clamps to the start and end", () => {
    expect(locate(tl, -5_000)).toEqual({ index: 0, offsetMs: 0 });
    expect(locate(tl, 999_999).index).toBe(2);
  });

  it("+30 s crosses into the next segment", () => {
    // 25 s into segment 0, skip forward 30 s -> 25 s into segment 1
    expect(locate(tl, tl.offsets[0] + 25_000 + SEEK_MS)).toEqual({ index: 1, offsetMs: 25_000 });
  });

  it("-30 s crosses back into the previous segment", () => {
    // 5 s into segment 1, skip back 30 s -> 5 s into segment 0
    expect(locate(tl, tl.offsets[1] + 5_000 - SEEK_MS)).toEqual({ index: 0, offsetMs: 5_000 });
  });
});

describe("chapters", () => {
  const sections = [
    sec({ id: "a", seq: 0, level: 1, number: 1, first_segment_seq: 5, last_segment_seq: 9 }),
    sec({ id: "a1", seq: 1, level: 2, parent_id: "a", first_segment_seq: 5, last_segment_seq: 6 }),
    sec({ id: "b", seq: 2, level: 1, number: 2, first_segment_seq: 10, last_segment_seq: 19 }),
    sec({ id: "b1", seq: 3, level: 2, parent_id: "b", first_segment_seq: 10, last_segment_seq: 12 }),
    sec({ id: "c", seq: 4, level: 1, number: 3, first_segment_seq: 20, last_segment_seq: 29 }),
  ];
  const chapters = buildOutline(sections);

  it("nests topics under their chapter", () => {
    expect(chapters).toHaveLength(3);
    expect(chapters[0].topics.map((t) => t.id)).toEqual(["a1"]);
    expect(chapters[1].topics.map((t) => t.id)).toEqual(["b1"]);
    expect(chapters[2].topics).toHaveLength(0);
  });

  it("finds the next and previous chapter", () => {
    expect(adjacentChapterSeq(chapters, 12, 1)).toBe(20);
    expect(adjacentChapterSeq(chapters, 12, -1)).toBe(5);
    expect(adjacentChapterSeq(chapters, 25, 1)).toBeNull();
    expect(adjacentChapterSeq(chapters, 6, -1)).toBeNull();
  });

  it("front matter (before chapter 1) goes to chapter 1 next", () => {
    expect(adjacentChapterSeq(chapters, 2, 1)).toBe(5);
  });
});

describe("pages", () => {
  const segments = [seg(0, 1000, "1"), seg(1, 1000, "2"), seg(2, 1000, "3-4")];
  it("finds a page, including ranges", () => {
    expect(segmentForPage(segments, 2)).toBe(1);
    expect(segmentForPage(segments, 4)).toBe(2);
    expect(segmentForPage(segments, 99)).toBeNull();
  });
});

describe("voice command handler mapping", () => {
  const segments = Array.from({ length: 30 }, (_, i) => seg(i, 30_000, String(i + 1)));
  const sections = [
    sec({ id: "a", seq: 0, level: 1, first_segment_seq: 0, last_segment_seq: 9 }),
    sec({ id: "b", seq: 2, level: 1, first_segment_seq: 10, last_segment_seq: 29 }),
    sec({ id: "t", seq: 3, level: 2, parent_id: "b", first_segment_seq: 15, last_segment_seq: 19 }),
  ];
  const ctx = { chapters: buildOutline(sections), segments, sections };
  const run = (cmd: unknown) => commandToAction(cmd, ctx);

  it("maps the simple transport commands", () => {
    expect(run({ intent: "pause" })).toEqual({ type: "pause" });
    expect(run({ intent: "stop" })).toEqual({ type: "stop" });
    expect(run({ intent: "play" })).toEqual({ type: "play" });
    expect(run({ intent: "resume" })).toEqual({ type: "play" });
    expect(run({ intent: "forward" })).toEqual({ type: "seek", deltaMs: SEEK_MS });
    expect(run({ intent: "backward" })).toEqual({ type: "seek", deltaMs: -SEEK_MS });
    expect(run({ intent: "faster" })).toEqual({ type: "rate", dir: 1 });
    expect(run({ intent: "slower" })).toEqual({ type: "rate", dir: -1 });
    expect(run({ intent: "next_chapter" })).toEqual({ type: "chapter", dir: 1 });
    expect(run({ action: "PREVIOUS-CHAPTER" })).toEqual({ type: "chapter", dir: -1 });
  });

  it("go to chapter / topic / page uses the resolved target", () => {
    expect(run({ intent: "go_chapter", target: { section_seq: 2 } })).toEqual({ type: "goto", seq: 10 });
    expect(run({ intent: "play_topic", target: { section_seq: 3 } })).toEqual({ type: "goto", seq: 15 });
    expect(run({ intent: "go_page", target: { page: 7 } })).toEqual({ type: "goto", seq: 6 });
    expect(run({ intent: "go_page", target: { segment_seq: 21 } })).toEqual({ type: "goto", seq: 21 });
  });

  it("does nothing when the target was not found", () => {
    expect(run({ intent: "go_chapter", target: { section_seq: 99 } })).toBeNull();
    expect(run({ intent: "play_topic", target: {} })).toBeNull();
    expect(run({ intent: "not_found" })).toBeNull();
    expect(run({ intent: "help" })).toBeNull();
  });
});

describe("wantsAudiobook (cross-book voice navigation)", () => {
  it("returns the book id for play/chapter/topic/page commands", () => {
    expect(wantsAudiobook({ intent: "play", target: { audiobook_id: "abc" } })).toBe("abc");
    expect(wantsAudiobook({ intent: "go_chapter", target: { audiobook_id: "abc" } })).toBe("abc");
  });
  it("ignores pause, help, not-found and commands without a book", () => {
    expect(wantsAudiobook({ intent: "pause", target: { audiobook_id: "abc" } })).toBeNull();
    expect(wantsAudiobook({ intent: "help", target: { audiobook_id: "abc" } })).toBeNull();
    expect(wantsAudiobook({ intent: "not_found", target: { audiobook_id: "abc" } })).toBeNull();
    expect(wantsAudiobook({ intent: "play", target: {} })).toBeNull();
  });
});
