import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { quizzesApi } from "@/features/quizzes/api";
import type { QuizCreateInput } from "@/types";

export const quizKeys = {
  list: (classroomId: string) => ["quizzes", "list", classroomId] as const,
  myAttempt: (id: string) => ["quizzes", "my-attempt", id] as const,
  results: (id: string) => ["quizzes", "results", id] as const,
};

export function useQuizzes(classroomId: string) {
  return useQuery({
    queryKey: quizKeys.list(classroomId),
    queryFn: () => quizzesApi.list(classroomId),
  });
}

export function useCreateQuiz(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: QuizCreateInput) => quizzesApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.list(classroomId) }),
  });
}
