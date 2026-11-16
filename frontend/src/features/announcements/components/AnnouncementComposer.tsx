import { useRef, useState, type FormEvent } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCreateAnnouncement } from "@/features/announcements/hooks";

/** Teacher-only form at the top of the stream. */
export function AnnouncementComposer({
  classroomId,
  onAnnounced,
}: {
  classroomId: string;
  onAnnounced: (message: string | null) => void;
}) {
  const create = useCreateAnnouncement(classroomId);
  const [content, setContent] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);
  // Guards two submit events in the same tick, before `isPending` has re-rendered the button.
  const inFlight = useRef(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    const text = content.trim();
    if (!text) {
      setFieldError("Write something to announce.");
      document.getElementById("announcement-content")?.focus();
      return;
    }
    setFieldError(null);
    onAnnounced(null);
    inFlight.current = true;
    create.mutate(text, {
      onSuccess: () => {
        setContent("");
        onAnnounced("Announcement posted.");
      },
      onSettled: () => {
        inFlight.current = false;
      },
    });
  }

  return (
    <Card>
      <CardContent className="p-4">
        <form onSubmit={onSubmit} noValidate className="space-y-3">
          <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />
          <TextAreaField
            id="announcement-content"
            label="Announce something to your class"
            rows={3}
            maxLength={10_000}
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setFieldError(null);
            }}
            error={fieldError}
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Posting…" : "Post"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
