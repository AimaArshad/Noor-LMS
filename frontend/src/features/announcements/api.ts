import { api } from "@/api/client";
import type { Announcement, Page } from "@/types";

export const announcementsApi = {
  list: (classroomId: string, params: { limit: number; offset: number }) =>
    api
      .get<Page<Announcement>>(`/classrooms/${classroomId}/announcements`, { params })
      .then((r) => r.data),

  /** Classroom teachers only. */
  create: (classroomId: string, content: string) =>
    api.post<Announcement>(`/classrooms/${classroomId}/announcements`, { content }).then((r) => r.data),

  /** Classroom teachers only; the announcement's comments are deleted with it. */
  remove: (classroomId: string, id: string) =>
    api.delete(`/classrooms/${classroomId}/announcements/${id}`).then(() => undefined),
};
