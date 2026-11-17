import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState, type KeyboardEvent } from "react";
import { useForm } from "react-hook-form";

import { getErrorMessage } from "@/api/errors";
import { Announcer } from "@/components/common/Announcer";
import { AsyncList } from "@/components/common/AsyncList";
import { AttachmentList } from "@/components/common/AttachmentList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  SUBMISSIONS_PAGE_SIZE,
  useGradeSubmission,
  useReturnSubmission,
  useSubmissionsPage,
} from "@/features/assignments/hooks";
import { gradeFormSchema, type GradeFormValues } from "@/features/assignments/schemas";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Submission } from "@/types";

const STATE_LABEL: Record<string, { label: string; variant: "secondary" | "default" | "outline" }> = {
  turned_in: { label: "To grade", variant: "secondary" },
  graded: { label: "Graded", variant: "outline" },
  returned: { label: "Returned", variant: "default" },
};

function SubmissionRow({
  submission,
  assignment,
  readOnly,
  onAnnounced,
}: {
  submission: Submission;
  assignment: Assignment;
  readOnly: boolean;
  onAnnounced: (message: string) => void;
}) {
  const schema = useMemo(() => gradeFormSchema(assignment.max_points), [assignment.max_points]);
  const grade = useGradeSubmission(assignment.id);
  const ret = useReturnSubmission(assignment.id);
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<GradeFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      grade: submission.grade === null ? "" : String(submission.grade),
      feedback: submission.feedback ?? "",
    },
  });

  const name = submission.student?.full_name ?? "Unknown student";
  const state = STATE_LABEL[submission.state] ?? STATE_LABEL.turned_in;
  const busy = grade.isPending || ret.isPending;
  const error = grade.isError ? grade.error : ret.isError ? ret.error : null;

  const save = handleSubmit((values) => {
    ret.reset();
    grade.mutate(
      {
        submissionId: submission.id,
        grade: Number(values.grade),
        feedback: values.feedback.trim(),
      },
      { onSuccess: () => onAnnounced(`Grade saved for ${name}.`) },
    );
  });

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void save();
    }
  }

  return (
    <tr className="align-top">
      <th scope="row" className="min-w-40 px-4 py-3 text-left font-medium">
        {name}
        <details className="mt-2 text-sm font-normal">
          <summary className="cursor-pointer text-primary">View work</summary>
          <div className="mt-2 space-y-3">
            {submission.content ? (
              <p className="whitespace-pre-wrap break-words rounded-md bg-muted/50 p-3">{submission.content}</p>
            ) : (
              <p className="text-muted-foreground">No text answer.</p>
            )}
            <AttachmentList attachments={submission.attachments} label={`Files from ${name}`} />
          </div>
        </details>
      </th>
      <td className="px-4 py-3">
        <Badge variant={state.variant}>{state.label}</Badge>
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        {submission.submitted_at ? (
          <time dateTime={submission.submitted_at}>{formatDateTime(submission.submitted_at)}</time>
        ) : (
          "—"
        )}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <Input
            aria-label={`Grade for ${name}`}
            aria-invalid={errors.grade ? true : undefined}
            inputMode="decimal"
            autoComplete="off"
            disabled={readOnly || busy}
            className="w-20"
            onKeyDown={onKeyDown}
            {...register("grade")}
          />
          <span className="text-muted-foreground">/ {assignment.max_points}</span>
        </div>
        {errors.grade ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {errors.grade.message}
          </p>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <Input
          aria-label={`Feedback for ${name}`}
          aria-invalid={errors.feedback ? true : undefined}
          autoComplete="off"
          disabled={readOnly || busy}
          className="min-w-48"
          onKeyDown={onKeyDown}
          {...register("feedback")}
        />
        {errors.feedback ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {errors.feedback.message}
          </p>
        ) : null}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={readOnly || busy || !isDirty} onClick={() => void save()}>
            {grade.isPending ? "Saving…" : "Save grade"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={readOnly || busy || isDirty || submission.state === "returned"}
            onClick={() => {
              grade.reset();
              ret.mutate(submission.id, { onSuccess: () => onAnnounced(`Work returned to ${name}.`) });
            }}
          >
            {ret.isPending ? "Returning…" : "Return"}
            <span className="sr-only"> work to {name}</span>
          </Button>
        </div>
        {isDirty ? <p className="mt-1 text-xs text-muted-foreground">Save before returning.</p> : null}
        <ErrorAlert className="mt-2" message={error ? getErrorMessage(error) : null} />
      </td>
    </tr>
  );
}

export function SubmissionsTable({ assignment, readOnly }: { assignment: Assignment; readOnly: boolean }) {
  const [offset, setOffset] = useState(0);
  const [status, setStatus] = useState("");
  const query = useSubmissionsPage(assignment.id, offset);
  const data = query.data;

  return (
    <section aria-labelledby="submissions-title" className="space-y-3">
      <Announcer message={status} />
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="submissions-title" className="text-xl font-semibold">
          Submissions
        </h2>
        {data ? (
          <p className="text-sm text-muted-foreground">
            {data.total} turned in · {data.not_submitted_count} not submitted
          </p>
        ) : null}
      </div>

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={data?.items.length === 0 && offset === 0}
        emptyText="Nobody has turned in work yet."
        loadingLabel="Loading submissions…"
      >
        <div className="relative overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Student submissions for {assignment.title}</caption>
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">
                  Student
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Status
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Turned in
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Grade
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Feedback
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data?.items.map((s) => (
                // The key includes the server state so a saved row resets its form to the new values.
                <SubmissionRow
                  key={`${s.id}:${s.state}:${s.graded_at ?? ""}:${s.updated_at}`}
                  submission={s}
                  assignment={assignment}
                  readOnly={readOnly}
                  onAnnounced={setStatus}
                />
              ))}
            </tbody>
          </table>
        </div>
        {data && data.total > SUBMISSIONS_PAGE_SIZE ? (
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - SUBMISSIONS_PAGE_SIZE))}
            >
              Previous
            </Button>
            <p className="text-sm text-muted-foreground">
              {offset + 1}–{Math.min(offset + SUBMISSIONS_PAGE_SIZE, data.total)} of {data.total}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + SUBMISSIONS_PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + SUBMISSIONS_PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
