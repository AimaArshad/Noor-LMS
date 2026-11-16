import { api } from "@/api/client";
import type {
  Assignment,
  AssignmentCreateInput,
  AssignmentState,
  AttachmentRef,
  Page,
  Submission,
  SubmissionList,
} from "@/types";

export interface AssignmentPayload extends AssignmentCreateInput {
  attachments?: AttachmentRef[];
}

export interface SubmitInput {
  content?: string;
  attachments: AttachmentRef[];
}

export const assignmentsApi = {
  /** Students only receive published assignments. */
  list: (classroomId: string) =>
    api
      .get<Page<Assignment>>(`/classrooms/${classroomId}/assignments`, { params: { limit: 100 } })
      .then((r) => r.data),

  get: (id: string) => api.get<Assignment>(`/assignments/${id}`).then((r) => r.data),

  create: (classroomId: string, body: AssignmentPayload) =>
    api.post<Assignment>(`/classrooms/${classroomId}/assignments`, body).then((r) => r.data),

  update: (id: string, body: { state?: AssignmentState }) =>
    api.patch<Assignment>(`/assignments/${id}`, body).then((r) => r.data),

  /** Students: create or update your submission (state becomes turned_in). */
  submit: (id: string, body: SubmitInput) =>
    api.post<Submission>(`/assignments/${id}/submit`, body).then((r) => r.data),

  /** Students: your own submission, or `null` when you have not turned anything in. */
  mySubmission: (id: string) =>
    api.get<Submission | null>(`/assignments/${id}/my-submission`).then((r) => r.data),

  /** Teachers: first 100 submissions plus `not_submitted_count` (used by the Grades tab). */
  submissions: (id: string) =>
    api.get<SubmissionList>(`/assignments/${id}/submissions`, { params: { limit: 100 } }).then((r) => r.data),

  submissionsPage: (id: string, params: { limit: number; offset: number }) =>
    api.get<SubmissionList>(`/assignments/${id}/submissions`, { params }).then((r) => r.data),

  grade: (submissionId: string, body: { grade: number; feedback: string }) =>
    api.patch<Submission>(`/submissions/${submissionId}/grade`, body).then((r) => r.data),

  /** Makes grade and feedback visible to the student and notifies them. */
  returnWork: (submissionId: string) =>
    api.patch<Submission>(`/submissions/${submissionId}/return`).then((r) => r.data),
};
