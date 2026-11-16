import { api } from "@/api/client";
import type { CommentRecord, CommentTarget, Page } from "@/types";

export const commentsApi = {
  list: (targetType: CommentTarget, targetId: string) =>
    api
      .get<Page<CommentRecord>>("/comments", {
        params: { target_type: targetType, target_id: targetId, limit: 100 },
      })
      .then((r) => r.data),

  create: (targetType: CommentTarget, targetId: string, body: string) =>
    api
      .post<CommentRecord>("/comments", { target_type: targetType, target_id: targetId, body })
      .then((r) => r.data),

  /** The author, or a classroom teacher. */
  remove: (id: string) => api.delete(`/comments/${id}`).then(() => undefined),
};
