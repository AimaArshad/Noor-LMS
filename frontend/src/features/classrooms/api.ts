import { api } from "@/api/client";
import type { Classroom } from "@/types";

export const classroomsApi = {
  list: (params?: { include_archived?: boolean }) =>
    api.get<Classroom[]>("/classrooms", { params }).then((r) => r.data),

  get: (id: string) => api.get<Classroom>(`/classrooms/${id}`).then((r) => r.data),
};
