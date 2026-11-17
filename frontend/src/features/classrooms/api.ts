import { api } from "@/api/client";
import type { Classroom, ClassroomCreateInput, ClassroomPeople } from "@/types";

export const classroomsApi = {
  list: (params?: { include_archived?: boolean; limit?: number; offset?: number }) =>
    api.get<Classroom[]>("/classrooms", { params }).then((r) => r.data),

  get: (id: string) => api.get<Classroom>(`/classrooms/${id}`).then((r) => r.data),

  /** Teachers/admins only (the API answers 403 otherwise). */
  create: (body: ClassroomCreateInput) => api.post<Classroom>("/classrooms", body).then((r) => r.data),

  /** Joins as a student. 404 = unknown code, 409 = already a member, 403 = archived. */
  join: (joinCode: string) =>
    api.post<Classroom>("/classrooms/join", { join_code: joinCode }).then((r) => r.data),

  /** Teachers in full, students one page (100 is the API maximum). */
  people: (id: string) =>
    api.get<ClassroomPeople>(`/classrooms/${id}/people`, { params: { limit: 100 } }).then((r) => r.data),
};
