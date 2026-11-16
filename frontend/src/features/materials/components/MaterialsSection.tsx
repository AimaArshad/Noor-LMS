import { Paperclip, Trash2 } from "lucide-react";
import { useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { StatusMessage } from "@/components/common/StatusMessage";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CreateMaterialDialog } from "@/features/materials/components/CreateMaterialDialog";
import { useDeleteMaterial, useMaterials } from "@/features/materials/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, Material } from "@/types";

function MaterialItem({
  material,
  classroom,
  onAnnounced,
}: {
  material: Material;
  classroom: Classroom;
  onAnnounced: (message: string | null) => void;
}) {
  const remove = useDeleteMaterial(classroom.id);
  const canDelete = classroom.my_role === "teacher" && !classroom.is_archived;
  const attachments = material.attachments ?? [];

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{material.title}</h3>
            <p className="text-sm text-muted-foreground">
              Posted <time dateTime={material.created_at}>{formatDateTime(material.created_at)}</time>
            </p>
          </div>
          {canDelete ? (
            <ConfirmDialog
              title="Delete this material?"
              description={`“${material.title}” will be removed for everyone in the class. This cannot be undone.`}
              onConfirm={() => {
                onAnnounced(null);
                remove.mutate(material.id, {
                  onSuccess: () => onAnnounced(`Deleted “${material.title}”.`),
                });
              }}
              trigger={
                <Button type="button" variant="ghost" size="sm" disabled={remove.isPending}>
                  <Trash2 aria-hidden="true" />
                  <span className="sr-only">Delete {material.title}</span>
                </Button>
              }
            />
          ) : null}
        </div>
        {material.description ? (
          <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm">{material.description}</p>
        ) : null}
        {attachments.length > 0 ? (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Paperclip className="h-3 w-3" aria-hidden="true" />
            {attachments.length} attachment{attachments.length === 1 ? "" : "s"}
          </p>
        ) : null}
        <ErrorAlert message={remove.isError ? getErrorMessage(remove.error) : null} />
      </CardContent>
    </Card>
  );
}

export function MaterialsSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useMaterials(classroom.id);
  const [status, setStatus] = useState<string | null>(null);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="materials-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="materials-title" className="text-xl font-semibold">
          Materials
        </h2>
        {canCreate ? <CreateMaterialDialog classroomId={classroom.id} /> : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No materials yet."
        loadingLabel="Loading materials…"
      >
        <ul className="space-y-3">
          {data?.items.map((material) => (
            <li key={material.id}>
              <MaterialItem material={material} classroom={classroom} onAnnounced={setStatus} />
            </li>
          ))}
        </ul>
      </AsyncList>
      <StatusMessage message={status} />
    </section>
  );
}
