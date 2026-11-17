import { api } from "@/api/client";
import type { TodoItem, TodoList } from "@/types";

export const todoApi = {
  /** Explicit items plus derived pending work. 100 is the API maximum. */
  list: () => api.get<TodoList>("/todo", { params: { limit: 100 } }).then((r) => r.data),

  /** Work that is already turned in always stays done, whatever you send. */
  mark: (id: string, isDone: boolean) =>
    api.patch<TodoItem>(`/todo/${id}`, { is_done: isDone }).then((r) => r.data),
};
