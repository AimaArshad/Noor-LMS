import { useQueries } from "@tanstack/react-query";
import { useState } from "react";

import { AsyncList } from "@/components/common/AsyncList";
import { assignmentsApi } from "@/features/assignments/api";
import { assignmentKeys, useAssignments } from "@/features/assignments/hooks";
import { quizzesApi } from "@/features/quizzes/api";
import { quizKeys, useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";

interface Row {
  key: string;
  kind: "Assignment" | "Quiz";
  title: string;
  due: string | null;
  status: string;
  score: string;
}

/** A student's own status and score for every published assignment and quiz. */
export function StudentGrades({ classroomId }: { classroomId: string }) {
  const assignments = useAssignments(classroomId);
  const quizzes = useQuizzes(classroomId);
  const assignmentItems = assignments.data?.items ?? [];
  const quizItems = quizzes.data?.items ?? [];

  const submissions = useQueries({
    queries: assignmentItems.map((a) => ({
      queryKey: assignmentKeys.mySubmission(a.id),
      queryFn: () => assignmentsApi.mySubmission(a.id),
    })),
  });
  const attempts = useQueries({
    queries: quizItems.map((q) => ({
      queryKey: quizKeys.myAttempt(q.id),
      queryFn: () => quizzesApi.myAttempt(q.id),
    })),
  });

  const now = useState(() => Date.now())[0];
  const rows: Row[] = [
    ...assignmentItems.map((a, i): Row => {
      const result = submissions[i];
      const submission = result?.data;
      let status = "…";
      let score = "—";
      if (result?.isError) status = "Unavailable";
      else if (result && !result.isPending) {
        if (!submission) status = a.due_at && new Date(a.due_at).getTime() < now ? "Missing" : "Not turned in";
        else if (submission.state === "returned") {
          status = "Returned";
          if (submission.grade !== null && submission.grade !== undefined) {
            score = `${formatPoints(submission.grade)} / ${formatPoints(a.max_points)}`;
          }
        } else status = "Turned in"; // graded work stays hidden until the teacher returns it
      }
      return { key: `a-${a.id}`, kind: "Assignment", title: a.title, due: a.due_at ?? null, status, score };
    }),
    ...quizItems.map((q, i): Row => {
      const result = attempts[i];
      const attempt = result?.data?.attempt;
      let status = "…";
      let score = "—";
      if (result?.isError) status = "Unavailable";
      else if (result && !result.isPending) {
        if (!attempt) status = "Not started";
        else if (!attempt.submitted_at) status = "In progress";
        else {
          status = attempt.pending_manual_grading ? "Awaiting grading" : "Submitted";
          if (attempt.score !== null && attempt.score !== undefined && attempt.max_score !== null && attempt.max_score !== undefined) {
            score = `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`;
          }
        }
      }
      return { key: `q-${q.id}`, kind: "Quiz", title: q.title, due: q.due_at ?? null, status, score };
    }),
  ];

  const isPending = assignments.isPending || quizzes.isPending;
  const error = assignments.error ?? quizzes.error;

  return (
    <AsyncList
      isPending={isPending}
      error={error}
      onRetry={() => {
        void assignments.refetch();
        void quizzes.refetch();
      }}
      isEmpty={rows.length === 0}
      emptyText="Nothing to grade yet. Published assignments and quizzes will appear here."
      loadingLabel="Loading your grades…"
    >
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Your work and scores in this class</caption>
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Work</th>
              <th scope="col" className="px-4 py-2 font-medium">Type</th>
              <th scope="col" className="px-4 py-2 font-medium">Due</th>
              <th scope="col" className="px-4 py-2 font-medium">Status</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row" className="px-4 py-3 font-medium">{row.title}</th>
                <td className="px-4 py-3">{row.kind}</td>
                <td className="whitespace-nowrap px-4 py-3">{row.due ? formatDateTime(row.due) : "—"}</td>
                <td className="px-4 py-3">{row.status}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right">{row.score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AsyncList>
  );
}
