import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assignmentsApi, type AssignmentPayload, type SubmitInput } from "@/features/assignments/api";
import type { AssignmentState } from "@/types";

export const SUBMISSIONS_PAGE_SIZE = 25;

export const assignmentKeys = {
  all: ["assignments"] as const,
  list: (classroomId: string) => ["assignments", "list", classroomId] as const,
  detail: (id: string) => ["assignments", "detail", id] as const,
  mySubmission: (id: string) => ["assignments", "my-submission", id] as const,
  /** Prefix of every submissions query of one assignment (the Grades tab and the table). */
  submissions: (id: string) => ["assignments", "submissions", id] as const,
  submissionsPage: (id: string, offset: number) =>
    ["assignments", "submissions", id, "page", offset] as const,
};

export function useAssignments(classroomId: string) {
  return useQuery({
    queryKey: assignmentKeys.list(classroomId),
    queryFn: () => assignmentsApi.list(classroomId),
  });
}

export function useAssignment(id: string) {
  return useQuery({
    queryKey: assignmentKeys.detail(id),
    queryFn: () => assignmentsApi.get(id),
    enabled: Boolean(id),
  });
}

export function useCreateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignmentPayload) => assignmentsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}

export function useUpdateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: AssignmentState }) =>
      assignmentsApi.update(id, { state }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.all }),
    meta: { classroomId },
  });
}

export function useMySubmission(id: string) {
  return useQuery({
    queryKey: assignmentKeys.mySubmission(id),
    queryFn: () => assignmentsApi.mySubmission(id),
  });
}

export function useSubmitAssignment(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitInput) => assignmentsApi.submit(assignmentId, body),
    onSuccess: (submission) => {
      queryClient.setQueryData(assignmentKeys.mySubmission(assignmentId), submission);
      void queryClient.invalidateQueries({ queryKey: ["todo"] });
    },
  });
}

export function useSubmissionsPage(assignmentId: string, offset: number) {
  return useQuery({
    queryKey: assignmentKeys.submissionsPage(assignmentId, offset),
    queryFn: () => assignmentsApi.submissionsPage(assignmentId, { limit: SUBMISSIONS_PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  });
}

export function useGradeSubmission(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      submissionId,
      grade,
      feedback,
    }: {
      submissionId: string;
      grade: number;
      feedback: string;
    }) => assignmentsApi.grade(submissionId, { grade, feedback }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.submissions(assignmentId) }),
  });
}

export function useReturnSubmission(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (submissionId: string) => assignmentsApi.returnWork(submissionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.submissions(assignmentId) }),
  });
}
