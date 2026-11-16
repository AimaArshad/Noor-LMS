import { MessageSquare, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { StatusMessage } from "@/components/common/StatusMessage";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useComments, useCreateComment, useDeleteComment } from "@/features/comments/hooks";
import { formatDateTime } from "@/lib/format";
import { useAuthStore } from "@/store/auth";
import type { Announcement, Classroom } from "@/types";

function CommentsPanel({ announcement, classroom }: { announcement: Announcement; classroom: Classroom }) {
  const me = useAuthStore((s) => s.user);
  const comments = useComments("announcement", announcement.id);
  const create = useCreateComment("announcement", announcement.id);
  const remove = useDeleteComment("announcement", announcement.id);
  const [body, setBody] = useState("");
  const [status, setStatus] = useState<string | null>(null);

  const canModerate = classroom.my_role === "teacher";
  const readOnly = classroom.is_archived;
  const items = comments.data?.items ?? [];

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = body.trim();
    if (!text) return;
    setStatus(null);
    create.mutate(text, {
      onSuccess: () => {
        setBody("");
        setStatus("Comment posted.");
      },
    });
  }

  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <AsyncList
          isPending={comments.isPending}
          error={comments.error}
          onRetry={() => void comments.refetch()}
          isEmpty={items.length === 0}
          emptyText="No comments yet. Start the conversation."
          loadingLabel="Loading comments…"
        >
          <ul aria-label="Comments" className="space-y-4">
            {items.map((comment) => {
              const canDelete = !readOnly && (comment.author_id === me?.id || canModerate);
              const deleting = remove.isPending && remove.variables === comment.id;
              return (
                <li key={comment.id} className="rounded-md border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">{comment.author?.full_name ?? "Deleted user"}</p>
                    {canDelete ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-mr-2 -mt-1 h-7 px-2"
                        disabled={deleting}
                        onClick={() => {
                          setStatus(null);
                          remove.mutate(comment.id, { onSuccess: () => setStatus("Comment deleted.") });
                        }}
                      >
                        <Trash2 aria-hidden="true" />
                        <span className="sr-only">Delete comment by {comment.author?.full_name ?? "deleted user"}</span>
                      </Button>
                    ) : null}
                  </div>
                  <time dateTime={comment.created_at} className="text-xs text-muted-foreground">
                    {formatDateTime(comment.created_at)}
                  </time>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm">{comment.body}</p>
                </li>
              );
            })}
          </ul>
          {comments.data && comments.data.total > items.length ? (
            <p className="mt-3 text-xs text-muted-foreground">Showing the first {items.length} comments.</p>
          ) : null}
        </AsyncList>
        <ErrorAlert className="mt-3" message={remove.isError ? getErrorMessage(remove.error) : null} />
        <StatusMessage className="mt-3" message={status} />
      </div>

      {readOnly ? (
        <p className="text-sm text-muted-foreground">This class is archived, so new comments are disabled.</p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-2 border-t pt-4">
          <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />
          <TextAreaField
            id={`comment-${announcement.id}`}
            label="Add a comment"
            rows={3}
            maxLength={5_000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={create.isPending || !body.trim()}>
              {create.isPending ? "Posting…" : "Comment"}
            </Button>
          </div>
        </form>
      )}
    </>
  );
}

/** "Comments" button that opens a right-side drawer; comments load only when it opens. */
export function CommentsDrawer({ announcement, classroom }: { announcement: Announcement; classroom: Classroom }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm">
          <MessageSquare aria-hidden="true" />
          Comments
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Comments</SheetTitle>
          <SheetDescription className="line-clamp-3">{announcement.content}</SheetDescription>
        </SheetHeader>
        <CommentsPanel announcement={announcement} classroom={classroom} />
      </SheetContent>
    </Sheet>
  );
}
