import { api } from "@/api/client";
import type { MyAttempt, Page, QuizCreateInput, QuizResults, QuizSummary } from "@/types";

export const quizzesApi = {
  /** Students only receive published quizzes. */
  list: (classroomId: string) =>
    api
      .get<Page<QuizSummary>>(`/classrooms/${classroomId}/quizzes`, { params: { limit: 100 } })
      .then((r) => r.data),

  create: (classroomId: string, body: QuizCreateInput) =>
    api.post<unknown>(`/classrooms/${classroomId}/quizzes`, body).then((r) => r.data),

  /** Students: latest attempt, attempts used, and whether they can (re)start. */
  myAttempt: (id: string) => api.get<MyAttempt>(`/quizzes/${id}/my-attempt`).then((r) => r.data),

  /** Teachers: statistics (we only need the counters, so ask for one attempt). */
  results: (id: string) =>
    api.get<QuizResults>(`/quizzes/${id}/results`, { params: { limit: 1 } }).then((r) => r.data),
};
