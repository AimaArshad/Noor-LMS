import { api } from "@/api/client";
import type { Material, MaterialCreateInput, Page } from "@/types";

export const materialsApi = {
  list: (classroomId: string) =>
    api
      .get<Page<Material>>(`/classrooms/${classroomId}/materials`, { params: { limit: 100 } })
      .then((r) => r.data),

  /** Classroom teachers only; every student gets a notification. */
  create: (classroomId: string, body: MaterialCreateInput) =>
    api.post<Material>(`/classrooms/${classroomId}/materials`, body).then((r) => r.data),

  remove: (classroomId: string, id: string) =>
    api.delete(`/classrooms/${classroomId}/materials/${id}`).then(() => undefined),
};
