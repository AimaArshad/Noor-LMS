import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { announcementsApi } from "@/features/announcements/api";

const PAGE_SIZE = 20;

export const announcementKeys = {
  list: (classroomId: string) => ["announcements", "list", classroomId] as const,
};

/** Newest first; `fetchNextPage` loads the next 20. */
export function useAnnouncements(classroomId: string) {
  return useInfiniteQuery({
    queryKey: announcementKeys.list(classroomId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => announcementsApi.list(classroomId, { limit: PAGE_SIZE, offset: pageParam }),
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length;
      return last.items.length > 0 && next < last.total ? next : undefined;
    },
  });
}

export function useCreateAnnouncement(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => announcementsApi.create(classroomId, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: announcementKeys.list(classroomId) }),
  });
}

export function useDeleteAnnouncement(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => announcementsApi.remove(classroomId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: announcementKeys.list(classroomId) }),
  });
}
