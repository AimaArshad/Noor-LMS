import { useQuery } from "@tanstack/react-query";

import { classroomsApi } from "@/features/classrooms/api";

const root = ["classrooms"] as const;

export const classroomKeys = {
  all: root,
  list: () => [...root, "list"] as const,
  detail: (id: string) => [...root, "detail", id] as const,
};

export function useClassrooms() {
  return useQuery({ queryKey: classroomKeys.list(), queryFn: () => classroomsApi.list() });
}

export function useClassroom(id: string) {
  return useQuery({
    queryKey: classroomKeys.detail(id),
    queryFn: () => classroomsApi.get(id),
    enabled: Boolean(id),
  });
}
