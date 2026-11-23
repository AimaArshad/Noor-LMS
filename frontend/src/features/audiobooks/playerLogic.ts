/**
 * Pure helpers for the audiobook player (no React, no DOM) so they can be
 * unit-tested: timeline maths, chapter outline, page lookup and the mapping
 * from a resolved voice command to a player action.
 */
import type { SectionNode, SegmentInfo } from "./playerApi";

export const SEEK_MS = 30_000;
export const SPEEDS: readonly number[] = [0.75, 1, 1.25, 1.5, 1.75, 2];

export function isReady(seg: SegmentInfo): boolean {
  return String(seg.status).toLowerCase() === "ready";
}

// ---------------------------------------------------------------------------
// Timeline (all segments laid end to end)
// ---------------------------------------------------------------------------

export interface Timeline {
  /** Start of each segment (ms) on the global timeline. */
  offsets: number[];
  total: number;
}

export function buildTimeline(segments: SegmentInfo[]): Timeline {
  const offsets: number[] = [];
  let acc = 0;
  for (const s of segments) {
    offsets.push(acc);
    acc += s.duration_ms ?? 0;
  }
  return { offsets, total: acc };
}

/** Map a global position to (segment index, offset inside that segment). */
export function locate(tl: Timeline, ms: number): { index: number; offsetMs: number } {
  if (tl.offsets.length === 0) return { index: 0, offsetMs: 0 };
  const t = Math.max(0, Math.min(ms, Math.max(0, tl.total - 1)));
  let lo = 0;
  let hi = tl.offsets.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (tl.offsets[mid] <= t) lo = mid;
    else hi = mid - 1;
  }
  return { index: lo, offsetMs: t - tl.offsets[lo] };
}

// ---------------------------------------------------------------------------
// Outline
// ---------------------------------------------------------------------------

export interface Chapter {
  section: SectionNode;
  topics: SectionNode[];
}

/** Level-1 sections are chapters; level-2 sections are their topics. */
export function buildOutline(sections: SectionNode[]): Chapter[] {
  const sorted = [...sections].sort((a, b) => a.seq - b.seq);
  const chapters: Chapter[] = [];
  for (const s of sorted) {
    if (s.level === 1) {
      chapters.push({ section: s, topics: [] });
    } else if (s.level === 2) {
      const parent =
        chapters.find((c) => c.section.id === s.parent_id) ?? chapters[chapters.length - 1];
      parent?.topics.push(s);
    }
  }
  return chapters;
}

/** Index of the chapter containing segment `seq` (-1 = front matter). */
export function chapterIndexForSeq(chapters: Chapter[], seq: number): number {
  let found = -1;
  chapters.forEach((c, i) => {
    const first = c.section.first_segment_seq;
    if (first != null && first <= seq) found = i;
  });
  return found;
}

/** First segment of the next (dir=1) or previous (dir=-1) chapter, or null. */
export function adjacentChapterSeq(chapters: Chapter[], seq: number, dir: 1 | -1): number | null {
  const ci = chapterIndexForSeq(chapters, seq);
  if (dir > 0) {
    for (let i = ci + 1; i < chapters.length; i++) {
      const f = chapters[i].section.first_segment_seq;
      if (f != null) return f;
    }
    return null;
  }
  for (let i = ci - 1; i >= 0; i--) {
    const f = chapters[i].section.first_segment_seq;
    if (f != null) return f;
  }
  return null;
}

/** The topic (level 2) that contains segment `seq`, if any. */
export function topicForSeq(chapter: Chapter | undefined, seq: number): SectionNode | undefined {
  return chapter?.topics.find(
    (t) =>
      t.first_segment_seq != null &&
      t.last_segment_seq != null &&
      t.first_segment_seq <= seq &&
      seq <= t.last_segment_seq,
  );
}

// ---------------------------------------------------------------------------
// Pages
// ---------------------------------------------------------------------------

/** First segment whose page label is (or spans) `page`. Labels like "23" or "23-24". */
export function segmentForPage(segments: SegmentInfo[], page: number): number | null {
  for (const s of segments) {
    const nums = (s.page_label.match(/\d+/g) ?? []).map(Number);
    if (nums.length === 1 && nums[0] === page) return s.seq;
    if (nums.length >= 2 && nums[0] <= page && page <= nums[1]) return s.seq;
  }
  return null;
}

// ---------------------------------------------------------------------------
// Voice commands -> player actions
// ---------------------------------------------------------------------------

export type PlayerAction =
  | { type: "play" }
  | { type: "pause" }
  | { type: "stop" }
  | { type: "seek"; deltaMs: number }
  | { type: "rate"; dir: 1 | -1 }
  | { type: "chapter"; dir: 1 | -1 }
  | { type: "goto"; seq: number };

export interface PlayerContext {
  chapters: Chapter[];
  segments: SegmentInfo[];
  sections: SectionNode[];
}

function words(v: unknown): Set<string> {
  return new Set(
    String(v ?? "")
      .toLowerCase()
      .split(/[^a-z0-9]+/)
      .filter(Boolean),
  );
}

function num(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

function cmdWords(cmd: unknown): Set<string> {
  const c = (cmd ?? {}) as { intent?: unknown; action?: unknown };
  return new Set([...words(c.intent), ...words(c.action)]);
}

function cmdTarget(cmd: unknown): Record<string, unknown> {
  const t = (cmd as { target?: unknown } | null)?.target;
  return t && typeof t === "object" ? (t as Record<string, unknown>) : {};
}

/**
 * The audiobook a command wants opened, or null when the command is not a
 * "play something" request (help, pause, not-found, ...).
 */
export function wantsAudiobook(cmd: unknown): string | null {
  const id = cmdTarget(cmd).audiobook_id;
  if (typeof id !== "string" || !id) return null;
  const w = cmdWords(cmd);
  if (w.has("not") && w.has("found")) return null;
  if (w.has("pause") || w.has("stop") || w.has("help")) return null;
  const wants = ["play", "resume", "chapter", "topic", "page", "section", "go", "goto"];
  return wants.some((k) => w.has(k)) ? id : null;
}

/**
 * Translate a resolved voice command ({intent, action, target}) into a player
 * action. Returns null when nothing should happen (unknown / not found).
 * Matches on words in `intent` or `action`, so it tolerates naming variants
 * such as "next_chapter", "NEXT-CHAPTER" or "go_chapter".
 */
export function commandToAction(cmd: unknown, ctx: PlayerContext): PlayerAction | null {
  const w = cmdWords(cmd);
  const has = (...keys: string[]) => keys.some((k) => w.has(k));

  if (w.has("not") && w.has("found")) return null;
  if (has("stop")) return { type: "stop" };
  if (has("pause")) return { type: "pause" };
  if (has("forward", "skip", "ahead")) return { type: "seek", deltaMs: SEEK_MS };
  if (has("backward", "back", "rewind")) return { type: "seek", deltaMs: -SEEK_MS };
  if (has("faster") || (has("speed") && has("up"))) return { type: "rate", dir: 1 };
  if (has("slower") || (has("speed") && has("down"))) return { type: "rate", dir: -1 };
  if (has("next")) return { type: "chapter", dir: 1 };
  if (has("previous", "prev")) return { type: "chapter", dir: -1 };

  const t = cmdTarget(cmd);
  const segExists = (seq: number) => ctx.segments.some((s) => s.seq === seq);

  const segSeq = num(t.segment_seq);
  if (segSeq != null && segExists(segSeq)) return { type: "goto", seq: segSeq };

  const secSeq = num(t.section_seq);
  if (secSeq != null) {
    const sec = ctx.sections.find((s) => s.seq === secSeq);
    if (sec?.first_segment_seq != null && segExists(sec.first_segment_seq)) {
      return { type: "goto", seq: sec.first_segment_seq };
    }
  }

  const page = num(t.page);
  if (page != null) {
    const seq = segmentForPage(ctx.segments, page);
    if (seq != null) return { type: "goto", seq };
  }

  // A navigation request whose target could not be resolved must not start playing.
  if (has("chapter", "topic", "page", "section", "go", "goto")) return null;
  if (has("play", "resume", "start", "continue", "unpause")) return { type: "play" };
  return null;
}
