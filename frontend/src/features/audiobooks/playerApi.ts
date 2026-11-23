import { api } from "@/api/client";
import type { AudiobookListItem, AudiobookStatus } from "@/features/audiobooks/api";

// Mirrors backend/app/schemas/audiobooks.py (manifest part)

export interface SectionNode {
  id: string;
  seq: number;
  parent_id: string | null;
  level: number;
  number: number | null;
  title: string;
  start_page: number;
  end_page: number | null;
  first_segment_seq: number | null;
  last_segment_seq: number | null;
}

export interface SegmentInfo {
  seq: number;
  section_id: string | null;
  page_label: string;
  duration_ms: number | null;
  /** "pending" | "ready" | ... (compared case-insensitively to "ready") */
  status: string;
}

export interface PlaybackProgress {
  segment_seq: number;
  offset_ms: number;
  updated_at: string;
}

export interface AudiobookManifest {
  id: string;
  title: string;
  status: AudiobookStatus;
  error: string | null;
  page_count: number | null;
  total_duration_ms: number | null;
  progress_pct: number | null;
  sections: SectionNode[];
  segments: SegmentInfo[];
  progress: PlaybackProgress | null;
}

export const playerApi = {
  /** GET /audiobooks — everything the caller can access. */
  listAll: () =>
    api
      .get<AudiobookListItem[]>("/audiobooks", { params: { limit: 100 } })
      .then((r) => r.data),

  /** GET /audiobooks/{id}/manifest */
  manifest: (id: string) =>
    api.get<AudiobookManifest>(`/audiobooks/${id}/manifest`).then((r) => r.data),

  /**
   * GET one segment's MP3 as a Blob. The endpoint needs the Authorization
   * header, which an <audio src> cannot send, so we fetch it through the api
   * client and play it from an object URL.
   */
  segmentAudio: (id: string, seq: number) =>
    api
      .get<Blob>(`/audiobooks/${id}/segments/${seq}/audio`, { responseType: "blob" })
      .then((r) => r.data),

  /** PUT /audiobooks/{id}/progress */
  saveProgress: (id: string, body: { segment_seq: number; offset_ms: number }) =>
    api.put(`/audiobooks/${id}/progress`, body).then((r) => r.data),
};
