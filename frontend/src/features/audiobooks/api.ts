import { api } from "@/api/client";

// ---------------------------------------------------------------------------
// Types — mirrors backend/app/schemas/audiobooks.py
// ---------------------------------------------------------------------------

export type AudiobookStatus =
  | "queued"
  | "extracting"
  | "synthesizing"
  | "ready"
  | "failed"
  | "needs_ocr";

export interface AudiobookRead {
  id: string;
  classroom_id: string;
  file_id: string;
  title: string;
  status: AudiobookStatus;
  error: string | null;
  page_count: number | null;
  pages_approximate: boolean;
  total_duration_ms: number | null;
  voice: string | null;
  progress_pct: number | null;
  created_at: string;
  updated_at: string;
}

export interface AudiobookListItem {
  id: string;
  title: string;
  classroom_name: string;
  status: AudiobookStatus;
  error: string | null;
  progress_pct: number | null;
  page_count: number | null;
}

/** Statuses considered "in progress" — drives polling. */
export const BUILDING_STATUSES: AudiobookStatus[] = [
  "queued",
  "extracting",
  "synthesizing",
];

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const audiobooksApi = {
  /** List audiobooks for a specific classroom. */
  listForClassroom: (classroomId: string) =>
    api
      .get<AudiobookRead[]>(`/classrooms/${classroomId}/audiobooks`, { params: { limit: 100 } })
      .then((r) => r.data)
      .catch(() =>
        // Fallback: classroom scoped list may not exist; use global list
        api
          .get<AudiobookListItem[]>("/audiobooks", { params: { limit: 100 } })
          .then((r) => r.data),
      ),

  /** POST /classrooms/{classroom_id}/audiobooks */
  create: (classroomId: string, body: { file_id: string; title?: string }) =>
    api
      .post<AudiobookRead>(`/classrooms/${classroomId}/audiobooks`, body)
      .then((r) => r.data),

  /** POST /audiobooks/{id}/rebuild */
  rebuild: (id: string) =>
    api.post<AudiobookRead>(`/audiobooks/${id}/rebuild`).then((r) => r.data),

  /** DELETE /audiobooks/{id} */
  remove: (id: string) =>
    api.delete(`/audiobooks/${id}`).then(() => undefined),
};
