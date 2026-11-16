import { useState } from "react";

import { AsyncList } from "@/components/common/AsyncList";
import { StatusMessage } from "@/components/common/StatusMessage";
import { Button } from "@/components/ui/button";
import { AnnouncementComposer } from "@/features/announcements/components/AnnouncementComposer";
import { AnnouncementItem } from "@/features/announcements/components/AnnouncementItem";
import { useAnnouncements } from "@/features/announcements/hooks";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function StreamPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Stream`);
  const [status, setStatus] = useState<string | null>(null);

  const canPost = classroom.my_role === "teacher" && !classroom.is_archived;
  const query = useAnnouncements(classroom.id);
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section aria-labelledby="stream-title" className="mx-auto max-w-3xl space-y-4">
      <h2 id="stream-title" className="sr-only">
        Announcements
      </h2>

      {canPost ? <AnnouncementComposer classroomId={classroom.id} onAnnounced={setStatus} /> : null}
      <StatusMessage message={status} />

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={items.length === 0}
        emptyText={
          classroom.my_role === "teacher"
            ? "No announcements yet. Post the first one above."
            : "No announcements yet."
        }
        loadingLabel="Loading announcements…"
      >
        <ul className="space-y-4">
          {items.map((announcement) => (
            <li key={announcement.id}>
              <AnnouncementItem announcement={announcement} classroom={classroom} onAnnounced={setStatus} />
            </li>
          ))}
        </ul>
        {query.hasNextPage ? (
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {query.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
