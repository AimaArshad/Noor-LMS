import { Paperclip } from "lucide-react";
import { useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { StatusMessage } from "@/components/common/StatusMessage";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CreateAssignmentDialog } from "@/features/assignments/components/CreateAssignmentDialog";
import { useAssignments, useUpdateAssignment } from "@/features/assignments/hooks";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Classroom } from "@/types";

function AssignmentItem({ assignment, classroom }: { assignment: Assignment; classroom: Classroom }) {
  const update = useUpdateAssignment(classroom.id);
  const [status, setStatus] = useState<string | null>(null);
  const canPublish = classroom.my_role === "teacher" && !classroom.is_archived && assignment.state === "draft";
  const attachments = assignment.attachments ?? [];

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{assignment.title}</h3>
            <p className="text-sm text-muted-foreground">
              {assignment.due_at ? (
                <>
                  Due <time dateTime={assignment.due_at}>{formatDateTime(assignment.due_at)}</time>
                </>
              ) : (
                "No due date"
              )}
              {" · "}
              {assignment.max_points} points
            </p>
          </div>
          <div className="flex items-center gap-2">
            {assignment.state === "draft" ? <Badge variant="outline">Draft</Badge> : null}
            {canPublish ? (
              <Button
                type="button"
                size="sm"
                disabled={update.isPending}
                onClick={() => {
                  setStatus(null);
                  update.mutate(
                    { id: assignment.id, state: "published" },
                    { onSuccess: () => setStatus(`Published “${assignment.title}”.`) },
                  );
                }}
              >
                {update.isPending ? "Publishing…" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>

        {assignment.description ? (
          <p className="line-clamp-2 whitespace-pre-wrap break-words text-sm">{assignment.description}</p>
        ) : null}
        {attachments.length > 0 ? (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Paperclip className="h-3 w-3" aria-hidden="true" />
            {attachments.length} attachment{attachments.length === 1 ? "" : "s"}
          </p>
        ) : null}
        <ErrorAlert message={update.isError ? getErrorMessage(update.error) : null} />
        <StatusMessage message={status} />
      </CardContent>
    </Card>
  );
}

export function AssignmentsSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useAssignments(classroom.id);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="assignments-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="assignments-title" className="text-xl font-semibold">
          Assignments
        </h2>
        {canCreate ? <CreateAssignmentDialog classroomId={classroom.id} /> : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No assignments yet."
        loadingLabel="Loading assignments…"
      >
        <ul className="space-y-3">
          {data?.items.map((assignment) => (
            <li key={assignment.id}>
              <AssignmentItem assignment={assignment} classroom={classroom} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
