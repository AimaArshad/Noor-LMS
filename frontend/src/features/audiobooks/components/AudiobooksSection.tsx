import { useState } from "react";

import { AsyncList } from "@/components/common/AsyncList";
import { StatusMessage } from "@/components/common/StatusMessage";
import { AudiobookItemCard } from "@/features/audiobooks/components/AudiobookItem";
import { CreateAudiobookDialog } from "@/features/audiobooks/components/CreateAudiobookDialog";
import { useAudiobooks } from "@/features/audiobooks/hooks";
import { BUILDING_STATUSES } from "@/features/audiobooks/api";
import type { Classroom } from "@/types";

export function AudiobooksSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useAudiobooks(classroom.id);
  const [status, setStatus] = useState<string | null>(null);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  const items = Array.isArray(data) ? data : [];
  const anyBuilding = items.some((ab) =>
    BUILDING_STATUSES.includes(ab.status as (typeof BUILDING_STATUSES)[number]),
  );

  return (
    <section aria-labelledby="audiobooks-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="audiobooks-title" className="text-xl font-semibold">
          Audiobooks
        </h2>
        {canCreate ? <CreateAudiobookDialog classroomId={classroom.id} /> : null}
      </div>

      {/* Polling indicator */}
      {anyBuilding ? (
        <p className="text-xs text-muted-foreground" role="status" aria-live="polite">
          Building in progress — refreshing automatically…
        </p>
      ) : null}

      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={items.length === 0}
        emptyText="No audiobooks yet."
        loadingLabel="Loading audiobooks…"
      >
        <ul className="space-y-3">
          {items.map((item) => (
            <li key={item.id}>
              <AudiobookItemCard
                item={item}
                classroomId={classroom.id}
                isTeacher={classroom.my_role === "teacher"}
                isArchived={classroom.is_archived}
                onAnnounced={setStatus}
              />
            </li>
          ))}
        </ul>
      </AsyncList>

      <StatusMessage message={status} />
    </section>
  );
}

