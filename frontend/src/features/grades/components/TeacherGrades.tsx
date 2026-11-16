import { useQueries } from "@tanstack/react-query";

import { AsyncList } from "@/components/common/AsyncList";
import { assignmentsApi } from "@/features/assignments/api";
import { assignmentKeys, useAssignments } from "@/features/assignments/hooks";
import { quizzesApi } from "@/features/quizzes/api";
import { quizKeys, useQuizzes } from "@/features/quizzes/hooks";
import { formatPoints } from "@/lib/format";

const TH = "px-4 py-2 font-medium";

/** Class-wide progress per published assignment and quiz. */
export function TeacherGrades({ classroomId }: { classroomId: string }) {
  const assignments = useAssignments(classroomId);
  const quizzes = useQuizzes(classroomId);
  const published = (assignments.data?.items ?? []).filter((a) => a.state === "published");
  const publishedQuizzes = (quizzes.data?.items ?? []).filter((q) => q.published);

  const submissions = useQueries({
    queries: published.map((a) => ({
      queryKey: assignmentKeys.submissions(a.id),
      queryFn: () => assignmentsApi.submissions(a.id),
    })),
  });
  const results = useQueries({
    queries: publishedQuizzes.map((q) => ({
      queryKey: quizKeys.results(q.id),
      queryFn: () => quizzesApi.results(q.id),
    })),
  });

  return (
    <div className="space-y-8">
      <section aria-labelledby="grades-assignments">
        <h2 id="grades-assignments" className="mb-3 text-xl font-semibold">Assignments</h2>
        <AsyncList
          isPending={assignments.isPending}
          error={assignments.error}
          onRetry={() => void assignments.refetch()}
          isEmpty={published.length === 0}
          emptyText="No published assignments yet."
        >
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Submission progress per assignment</caption>
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th scope="col" className={TH}>Assignment</th>
                  <th scope="col" className={`${TH} text-right`}>Points</th>
                  <th scope="col" className={`${TH} text-right`}>Turned in</th>
                  <th scope="col" className={`${TH} text-right`}>To grade</th>
                  <th scope="col" className={`${TH} text-right`}>Graded / returned</th>
                  <th scope="col" className={`${TH} text-right`}>Not submitted</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {published.map((assignment, i) => {
                  const result = submissions[i];
                  const data = result?.data;
                  const cell = (value: number | undefined) =>
                    result?.isError ? "!" : data ? String(value ?? 0) : "…";
                  return (
                    <tr key={assignment.id}>
                      <th scope="row" className="px-4 py-3 font-medium">{assignment.title}</th>
                      <td className="px-4 py-3 text-right">{assignment.max_points}</td>
                      <td className="px-4 py-3 text-right">{cell(data?.total)}</td>
                      <td className="px-4 py-3 text-right">
                        {cell(data?.items.filter((s) => s.state === "turned_in").length)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {cell(data?.items.filter((s) => s.state === "graded" || s.state === "returned").length)}
                      </td>
                      <td className="px-4 py-3 text-right">{cell(data?.not_submitted_count)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncList>
      </section>

      <section aria-labelledby="grades-quizzes">
        <h2 id="grades-quizzes" className="mb-3 text-xl font-semibold">Quizzes</h2>
        <AsyncList
          isPending={quizzes.isPending}
          error={quizzes.error}
          onRetry={() => void quizzes.refetch()}
          isEmpty={publishedQuizzes.length === 0}
          emptyText="No published quizzes yet."
        >
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Results per quiz</caption>
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th scope="col" className={TH}>Quiz</th>
                  <th scope="col" className={`${TH} text-right`}>Submitted</th>
                  <th scope="col" className={`${TH} text-right`}>Not attempted</th>
                  <th scope="col" className={`${TH} text-right`}>Average (best attempts)</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {publishedQuizzes.map((quiz, i) => {
                  const result = results[i];
                  const data = result?.data;
                  const placeholder = result?.isError ? "!" : "…";
                  return (
                    <tr key={quiz.id}>
                      <th scope="row" className="px-4 py-3 font-medium">{quiz.title}</th>
                      <td className="px-4 py-3 text-right">{data ? data.submitted_count : placeholder}</td>
                      <td className="px-4 py-3 text-right">{data ? data.not_attempted_count : placeholder}</td>
                      <td className="px-4 py-3 text-right">
                        {data
                          ? data.average_score === null || data.average_score === undefined
                            ? "—"
                            : `${formatPoints(data.average_score)} / ${formatPoints(data.max_score)}`
                          : placeholder}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncList>
      </section>

      <p className="text-xs text-muted-foreground">
        Counts cover the first 100 submissions of each assignment. A per-student gradebook comes with the grading screens.
      </p>
    </div>
  );
}
