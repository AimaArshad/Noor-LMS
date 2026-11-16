import { Trash2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CommentsDrawer } from "@/features/announcements/components/CommentsDrawer";
import { useDeleteAnnouncement } from "@/features/announcements/hooks";
import { formatDateTime } from "@/lib/format";
import type { Announcement, Classroom } from "@/types";

export function AnnouncementItem({
  announcement,
  classroom,
  onAnnounced,
}: {
  announcement: Announcement;
  classroom: Classroom;
  onAnnounced: (message: string | null) => void;
}) {
  const remove = useDeleteAnnouncement(classroom.id);
  const canDelete = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-medium">{announcement.author?.full_name ?? "Deleted user"}</p>
            <time dateTime={announcement.created_at} className="text-xs text-muted-foreground">
              {formatDateTime(announcement.created_at)}
            </time>
          </div>
          {canDelete ? (
            <ConfirmDialog
              title="Delete this announcement?"
              description="It will be removed for everyone in the class, together with all of its comments. This cannot be undone."
              onConfirm={() => {
                onAnnounced(null);
                remove.mutate(announcement.id, { onSuccess: () => onAnnounced("Announcement deleted.") });
              }}
              trigger={
                <Button type="button" variant="ghost" size="sm" disabled={remove.isPending}>
                  <Trash2 aria-hidden="true" />
                  <span className="sr-only">Delete announcement</span>
                </Button>
              }
            />
          ) : null}
        </div>

        <p className="whitespace-pre-wrap break-words">{announcement.content}</p>
        <ErrorAlert message={remove.isError ? getErrorMessage(remove.error) : null} />

        <div className="border-t pt-2">
          <CommentsDrawer announcement={announcement} classroom={classroom} />
        </div>
      </CardContent>
    </Card>
  );
}
