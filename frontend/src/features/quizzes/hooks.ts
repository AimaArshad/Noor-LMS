import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { quizzesApi, type AnswerInput } from "@/features/quizzes/api";
import type { QuizCreatePayload } from "@/types";

export const RESULTS_PAGE_SIZE = 25;

export const quizKeys = {
  all: ["quizzes"] as const,
  list: (classroomId: string) => ["quizzes", "list", classroomId] as const,
  detail: (id: string) => ["quizzes", "detail", id] as const,
  myAttempt: (id: string) => ["quizzes", "my-attempt", id] as const,
  /** Prefix of every results query of one quiz (Grades tab statistics and the results table). */
  results: (id: string) => ["quizzes", "results", id] as const,
  resultsPage: (id: string, offset: number) => ["quizzes", "results", id, "page", offset] as const,
};

export function useQuizzes(classroomId: string) {
  return useQuery({
    queryKey: quizKeys.list(classroomId),
    queryFn: () => quizzesApi.list(classroomId),
  });
}

export function useQuiz(id: string) {
  return useQuery({
    queryKey: quizKeys.detail(id),
    queryFn: () => quizzesApi.get(id),
    enabled: Boolean(id),
  });
}

export function useCreateQuiz(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: QuizCreatePayload) => quizzesApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.list(classroomId) }),
  });
}

export function useUpdateQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (published: boolean) => quizzesApi.update(quizId, { published }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.all }),
  });
}

export function useMyAttempt(quizId: string) {
  return useQuery({
    queryKey: quizKeys.myAttempt(quizId),
    queryFn: () => quizzesApi.myAttempt(quizId),
  });
}

export function useStartQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quizzesApi.start(quizId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.myAttempt(quizId) }),
  });
}

export function useSubmitQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (answers: AnswerInput[]) => quizzesApi.submit(quizId, answers),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: quizKeys.myAttempt(quizId) });
      void queryClient.invalidateQueries({ queryKey: ["todo"] });
    },
  });
}

export function useQuizResultsPage(quizId: string, offset: number) {
  return useQuery({
    queryKey: quizKeys.resultsPage(quizId, offset),
    queryFn: () => quizzesApi.resultsPage(quizId, { limit: RESULTS_PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  });
}

export function useGradeAnswer(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { attemptId: string; questionId: string; points: number }) =>
      quizzesApi.gradeAnswer(quizId, v.attemptId, v.questionId, v.points),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.results(quizId) }),
  });
}
