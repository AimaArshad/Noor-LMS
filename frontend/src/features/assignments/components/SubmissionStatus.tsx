import { Badge } from "@/components/ui/badge";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { Assignment, Submission } from "@/types";

type Variant = "default" | "secondary" | "destructive" | "outline";

/** What the student sees. Grades appear only after the teacher returns the work. */
function describe(
  submission: Submission | null | undefined,
  assignment: Assignment,
): { label: string; variant: Variant } {
  if (!submission) {
    const overdue = assignment.due_at !== null && new Date(assignment.due_at) < new Date();
    return overdue ? { label: "Missing", variant: "destructive" } : { label: "Assigned", variant: "outline" };
  }
  if (submission.state === "returned") {
    return submission.grade !== null
      ? { label: "Graded", variant: "default" }
      : { label: "Returned", variant: "default" };
  }
  return { label: "Turned in", variant: "secondary" };
}

export function SubmissionStatus({
  submission,
  assignment,
}: {
  submission: Submission | null | undefined;
  assignment: Assignment;
}) {
  const { label, variant } = describe(submission, assignment);
  return (
    <section aria-labelledby="your-work-title" className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="your-work-title" className="text-lg font-semibold">
          Your work
        </h2>
        <Badge variant={variant}>{label}</Badge>
      </div>

      {submission?.submitted_at ? (
        <p className="text-sm text-muted-foreground">
          Turned in{" "}
          <time dateTime={submission.submitted_at}>{formatDateTime(submission.submitted_at)}</time>
        </p>
      ) : null}

      {submission?.state === "returned" && submission.grade !== null ? (
        <p className="text-2xl font-semibold">
          {formatPoints(submission.grade)}{" "}
          <span className="text-base font-normal text-muted-foreground">/ {assignment.max_points}</span>
        </p>
      ) : null}

      {submission?.state === "returned" && submission.feedback ? (
        <div className="rounded-md bg-muted/50 p-3 text-sm">
          <p className="font-medium">Teacher feedback</p>
          <p className="mt-1 whitespace-pre-wrap break-words">{submission.feedback}</p>
        </div>
      ) : null}
    </section>
  );
}
