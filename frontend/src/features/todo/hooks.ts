import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { todoApi } from "@/features/todo/api";

export const todoKeys = {
  all: ["todo"] as const,
  list: () => ["todo", "list"] as const,
};

export function useTodos() {
  return useQuery({ queryKey: todoKeys.list(), queryFn: todoApi.list });
}

export function useToggleTodo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, isDone }: { id: string; isDone: boolean }) => todoApi.mark(id, isDone),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: todoKeys.all }),
  });
}
