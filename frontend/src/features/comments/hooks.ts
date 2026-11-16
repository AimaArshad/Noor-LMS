import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { commentsApi } from "@/features/comments/api";
import type { CommentTarget } from "@/types";

export const commentKeys = {
  list: (targetType: CommentTarget, targetId: string) => ["comments", targetType, targetId] as const,
};

export function useComments(targetType: CommentTarget, targetId: string) {
  return useQuery({
    queryKey: commentKeys.list(targetType, targetId),
    queryFn: () => commentsApi.list(targetType, targetId),
  });
}

export function useCreateComment(targetType: CommentTarget, targetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => commentsApi.create(targetType, targetId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: commentKeys.list(targetType, targetId) }),
  });
}

export function useDeleteComment(targetType: CommentTarget, targetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => commentsApi.remove(commentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: commentKeys.list(targetType, targetId) }),
  });
}
