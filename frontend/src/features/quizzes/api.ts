import { api } from "@/api/client";
import type {
  AttemptResult,
  AttemptStart,
  MyAttempt,
  Page,
  QuizCreatePayload,
  QuizResults,
  QuizSummary,
  QuizView,
  TeacherQuiz,
} from "@/types";

export interface StartResponse {
  attempt: AttemptStart;
  /** true = new attempt (201), false = an open attempt was resumed (200) */
  created: boolean;
  /** The server clock (from the HTTP Date header), or null when it is not readable. */
  serverNow: number | null;
}

export interface AnswerInput {
  question_id: string;
  selected_option_id?: string;
  answer_text?: string;
}

export const quizzesApi = {
  /** Students only receive published quizzes. */
  list: (classroomId: string) =>
    api
      .get<Page<QuizSummary>>(`/classrooms/${classroomId}/quizzes`, { params: { limit: 100 } })
      .then((r) => r.data),

  /** Teachers get the answer key (`view: "teacher"`), students never do. */
  get: (id: string) => api.get<QuizView>(`/quizzes/${id}`).then((r) => r.data),

  create: (classroomId: string, body: QuizCreatePayload) =>
    api.post<TeacherQuiz>(`/classrooms/${classroomId}/quizzes`, body).then((r) => r.data),

  update: (id: string, body: { published: boolean }) =>
    api.patch<TeacherQuiz>(`/quizzes/${id}`, body).then((r) => r.data),

  start: (id: string): Promise<StartResponse> =>
    api.post<AttemptStart>(`/quizzes/${id}/start`).then((r) => {
      const parsed = Date.parse(String(r.headers["date"] ?? ""));
      return {
        attempt: r.data,
        created: r.status === 201,
        serverNow: Number.isNaN(parsed) ? null : parsed,
      };
    }),

  submit: (id: string, answers: AnswerInput[]) =>
    api.post<AttemptResult>(`/quizzes/${id}/submit`, { answers }).then((r) => r.data),

  myAttempt: (id: string) => api.get<MyAttempt>(`/quizzes/${id}/my-attempt`).then((r) => r.data),

  /** Statistics only (one attempt requested): used by the Grades tab. */
  results: (id: string) =>
    api.get<QuizResults>(`/quizzes/${id}/results`, { params: { limit: 1 } }).then((r) => r.data),

  resultsPage: (id: string, params: { limit: number; offset: number }) =>
    api.get<QuizResults>(`/quizzes/${id}/results`, { params }).then((r) => r.data),

  gradeAnswer: (quizId: string, attemptId: string, questionId: string, pointsAwarded: number) =>
    api
      .patch<AttemptResult>(`/quizzes/${quizId}/attempts/${attemptId}/answers/${questionId}`, {
        points_awarded: pointsAwarded,
      })
      .then((r) => r.data),
};
