import { api } from "@/api/client";
import type {
  Assignment,
  AssignmentCreateInput,
  AssignmentState,
  Page,
  Submission,
  SubmissionList,
} from "@/types";

export const assignmentsApi = {
  /** Students only receive published assignments. */
  list: (classroomId: string) =>
    api
      .get<Page<Assignment>>(`/classrooms/${classroomId}/assignments`, { params: { limit: 100 } })
      .then((r) => r.data),

  create: (classroomId: string, body: AssignmentCreateInput) =>
    api.post<Assignment>(`/classrooms/${classroomId}/assignments`, body).then((r) => r.data),

  update: (id: string, body: { state?: AssignmentState }) =>
    api.patch<Assignment>(`/assignments/${id}`, body).then((r) => r.data),

  /** Students: your own submission, or `null` when you have not turned anything in. */
  mySubmission: (id: string) =>
    api.get<Submission | null>(`/assignments/${id}/my-submission`).then((r) => r.data),

  /** Teachers: first 100 submissions plus `not_submitted_count`. */
  submissions: (id: string) =>
    api
      .get<SubmissionList>(`/assignments/${id}/submissions`, { params: { limit: 100 } })
      .then((r) => r.data),
};
