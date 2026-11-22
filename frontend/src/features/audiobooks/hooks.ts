import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { audiobooksApi, BUILDING_STATUSES } from "@/features/audiobooks/api";

export const audiobookKeys = {
  list: (classroomId: string) => ["audiobooks", "list", classroomId] as const,
};

/**
 * Fetch the classroom's audiobooks.
 * Polls every 5 s while any audiobook is building (queued / extracting / synthesizing).
 */
export function useAudiobooks(classroomId: string) {
  return useQuery({
    queryKey: audiobookKeys.list(classroomId),
    queryFn: () => audiobooksApi.listForClassroom(classroomId),
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!Array.isArray(data)) return false;
      const anyBuilding = data.some((ab) =>
        BUILDING_STATUSES.includes(ab.status as (typeof BUILDING_STATUSES)[number]),
      );
      return anyBuilding ? 5_000 : false;
    },
  });
}

export function useCreateAudiobook(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: { file_id: string; title?: string }) =>
      audiobooksApi.create(classroomId, body),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: audiobookKeys.list(classroomId) }),
  });
}

export function useRebuildAudiobook(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => audiobooksApi.rebuild(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: audiobookKeys.list(classroomId) }),
  });
}

export function useDeleteAudiobook(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => audiobooksApi.remove(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: audiobookKeys.list(classroomId) }),
  });
}
