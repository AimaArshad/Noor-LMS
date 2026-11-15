import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { classroomsApi } from "@/features/classrooms/api";
import type { Classroom } from "@/types";

const root = ["classrooms"] as const;

export const classroomKeys = {
  all: root,
  /** Prefix of every list query (archived or not): use it to invalidate. */
  lists: () => [...root, "list"] as const,
  list: (includeArchived: boolean) => [...root, "list", { includeArchived }] as const,
  detail: (id: string) => [...root, "detail", id] as const,
};

export function useClassrooms(options: { includeArchived?: boolean } = {}) {
  const includeArchived = options.includeArchived ?? false;
  return useQuery({
    queryKey: classroomKeys.list(includeArchived),
    // 100 is the API maximum; pagination UI comes later.
    queryFn: () => classroomsApi.list({ include_archived: includeArchived, limit: 100 }),
  });
}

export function useClassroom(id: string) {
  return useQuery({
    queryKey: classroomKeys.detail(id),
    queryFn: () => classroomsApi.get(id),
    enabled: Boolean(id),
  });
}

/** Shared by create and join: seed the detail cache (instant navigation), refresh the lists. */
function useRegisterNewClassroom() {
  const queryClient = useQueryClient();
  return (classroom: Classroom) => {
    queryClient.setQueryData(classroomKeys.detail(classroom.id), classroom);
    void queryClient.invalidateQueries({ queryKey: classroomKeys.lists() });
  };
}

export function useCreateClassroom() {
  const register = useRegisterNewClassroom();
  return useMutation({
    mutationFn: classroomsApi.create,
    onSuccess: register,
  });
}

export function useJoinClassroom() {
  const register = useRegisterNewClassroom();
  return useMutation({
    mutationFn: classroomsApi.join,
    onSuccess: register,
  });
}
