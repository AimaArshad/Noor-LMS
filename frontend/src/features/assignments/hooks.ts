import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assignmentsApi } from "@/features/assignments/api";
import type { AssignmentCreateInput, AssignmentState } from "@/types";

export const assignmentKeys = {
  list: (classroomId: string) => ["assignments", "list", classroomId] as const,
  mySubmission: (id: string) => ["assignments", "my-submission", id] as const,
  submissions: (id: string) => ["assignments", "submissions", id] as const,
};

export function useAssignments(classroomId: string) {
  return useQuery({
    queryKey: assignmentKeys.list(classroomId),
    queryFn: () => assignmentsApi.list(classroomId),
  });
}

export function useCreateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignmentCreateInput) => assignmentsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}

export function useUpdateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: AssignmentState }) => assignmentsApi.update(id, { state }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}
