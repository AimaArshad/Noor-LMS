import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { materialsApi } from "@/features/materials/api";
import type { MaterialCreateInput } from "@/types";

export const materialKeys = {
  list: (classroomId: string) => ["materials", "list", classroomId] as const,
};

export function useMaterials(classroomId: string) {
  return useQuery({
    queryKey: materialKeys.list(classroomId),
    queryFn: () => materialsApi.list(classroomId),
  });
}

export function useCreateMaterial(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MaterialCreateInput) => materialsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: materialKeys.list(classroomId) }),
  });
}

export function useDeleteMaterial(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => materialsApi.remove(classroomId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: materialKeys.list(classroomId) }),
  });
}
