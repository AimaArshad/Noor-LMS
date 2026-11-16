import { ArrowLeft } from "lucide-react";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getErrorMessage, getStatus } from "@/api/errors";
import { Announcer } from "@/components/common/Announcer";
import { AttachmentList } from "@/components/common/AttachmentList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SubmissionForm } from "@/features/assignments/components/SubmissionForm";
import { SubmissionStatus } from "@/features/assignments/components/SubmissionStatus";
import { SubmissionsTable } from "@/features/assignments/components/SubmissionsTable";
import { useAssignment, useMySubmission, useUpdateAssignment } from "@/features/assignments/hooks";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Classroom } from "@/types";

function StudentPanel({ assignment, classroom }: { assignment: Assignment; classroom: Classroom }) {
  const mine = useMySubmission(assignment.id);
  if (mine.isPending) return <Spinner label="Loading your work…" />;
  if (mine.isError) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(mine.error)} />
        <Button variant="outline" size="sm" onClick={() => void mine.refetch()}>
          Try again
        </Button>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <SubmissionStatus submission={mine.data} assignment={assignment} />
      <SubmissionForm
        key={mine.data?.id ?? "new"}
        assignmentId={assignment.id}
        submission={mine.data}
        disabled={classroom.is_archived}
      />
    </div>
  );
}

export function AssignmentPage() {
  const { classroom } = useClassroomContext();
  const { assignmentId = "" } = useParams();
  const { data: assignment, isPending, error, refetch } = useAssignment(assignmentId);
  const publish = useUpdateAssignment(classroom.id);
  const [status, setStatus] = useState("");
  useDocumentTitle(assignment ? `${assignment.title} · ${classroom.name}` : classroom.name);

  const back = (
    <Link
      to={`/classes/${classroom.id}/classwork`}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to classwork
    </Link>
  );

  if (isPending) return <Spinner label="Loading assignment…" />;
  if (error || !assignment || assignment.classroom_id !== classroom.id) {
    const missing = !error || getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="space-y-3 py-6">
        {back}
        <h2 className="text-xl font-semibold">
          {missing ? "Assignment not found" : "Could not load this assignment"}
        </h2>
        {!missing ? (
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Try again
          </Button>
        ) : null}
      </div>
    );
  }

  const isTeacher = classroom.my_role === "teacher";
  const canPublish = isTeacher && !classroom.is_archived && assignment.state === "draft";

  return (
    <article className="mx-auto max-w-4xl space-y-6">
      <Announcer message={status} />
      {back}

      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="break-words text-2xl font-semibold tracking-tight">{assignment.title}</h2>
          <div className="flex items-center gap-2">
            {assignment.state === "draft" ? <Badge variant="outline">Draft</Badge> : null}
            {canPublish ? (
              <Button
                size="sm"
                disabled={publish.isPending}
                onClick={() =>
                  publish.mutate(
                    { id: assignment.id, state: "published" },
                    { onSuccess: () => setStatus("Assignment published. Students can see it now.") },
                  )
                }
              >
                {publish.isPending ? "Publishing…" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>
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
        <ErrorAlert message={publish.isError ? getErrorMessage(publish.error) : null} />
      </header>

      {assignment.description ? (
        <p className="whitespace-pre-wrap break-words">{assignment.description}</p>
      ) : (
        <p className="text-muted-foreground">No instructions.</p>
      )}
      <AttachmentList attachments={assignment.attachments ?? []} label="Attachments" />

      <hr />

      {isTeacher ? (
        <SubmissionsTable assignment={assignment} readOnly={classroom.is_archived} />
      ) : (
        <StudentPanel assignment={assignment} classroom={classroom} />
      )}
    </article>
  );
}
