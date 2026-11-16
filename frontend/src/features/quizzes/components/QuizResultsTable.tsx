import { zodResolver } from "@hookform/resolvers/zod";
import { Fragment, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { getErrorMessage } from "@/api/errors";
import { Announcer } from "@/components/common/Announcer";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RESULTS_PAGE_SIZE, useGradeAnswer, useQuizResultsPage } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AnswerResult, AttemptResult, TeacherQuestion, TeacherQuiz } from "@/types";

function ManualGradeForm({
  quizId,
  attemptId,
  question,
  disabled,
  onSaved,
}: {
  quizId: string;
  attemptId: string;
  question: TeacherQuestion;
  disabled: boolean;
  onSaved: () => void;
}) {
  const grade = useGradeAnswer(quizId);
  const schema = useMemo(
    () =>
      z.object({
        points: z
          .string()
          .trim()
          .regex(/^\d+(\.\d{1,2})?$/, "Enter a number (up to 2 decimals).")
          .refine((v) => Number(v) <= question.points, `At most ${formatPoints(question.points)}.`),
      }),
    [question.points],
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ points: string }>({ resolver: zodResolver(schema), defaultValues: { points: "" } });

  const submit = handleSubmit(({ points }) =>
    grade.mutate(
      { attemptId, questionId: question.id, points: Number(points) },
      { onSuccess: onSaved },
    ),
  );

  return (
    <form onSubmit={(e) => void submit(e)} noValidate className="mt-2 flex flex-wrap items-start gap-2">
      <div>
        <Input
          aria-label="Points to award"
          inputMode="decimal"
          autoComplete="off"
          className="w-24"
          disabled={disabled || grade.isPending}
          aria-invalid={errors.points ? true : undefined}
          {...register("points")}
        />
        {errors.points ? (
          <p role="alert" className="mt-1 text-xs text-destructive">
            {errors.points.message}
          </p>
        ) : null}
      </div>
      <span className="pt-2 text-sm text-muted-foreground">/ {formatPoints(question.points)}</span>
      <Button type="submit" size="sm" disabled={disabled || grade.isPending}>
        {grade.isPending ? "Saving…" : "Save points"}
      </Button>
      <ErrorAlert className="basis-full" message={grade.isError ? getErrorMessage(grade.error) : null} />
    </form>
  );
}

function AttemptReview({
  quiz,
  attempt,
  readOnly,
  onAnnounced,
}: {
  quiz: TeacherQuiz;
  attempt: AttemptResult;
  readOnly: boolean;
  onAnnounced: (message: string) => void;
}) {
  if (attempt.answers.length === 0) {
    return <p className="text-sm text-muted-foreground">No answers were recorded for this attempt.</p>;
  }
  const byQuestion = new Map<string, AnswerResult>(attempt.answers.map((a) => [a.question_id, a]));
  return (
    <ol className="space-y-3">
      {quiz.questions.map((question, i) => {
        const answer = byQuestion.get(question.id);
        const chosen = answer?.selected_option_id
          ? question.options.find((o) => o.id === answer.selected_option_id)?.text
          : answer?.answer_text;
        const pending = answer !== undefined && answer.is_correct === null;
        return (
          <li key={question.id} className="rounded-md border bg-background p-3 text-sm">
            <p className="font-medium">
              <span className="text-muted-foreground">{i + 1}. </span>
              {question.prompt}
            </p>
            <p className="mt-1">
              <span className="text-muted-foreground">Answer: </span>
              {chosen ? (
                <span className="whitespace-pre-wrap break-words">{chosen}</span>
              ) : (
                <span className="italic">No answer</span>
              )}
            </p>
            <p className="text-muted-foreground">
              {pending
                ? "Awaiting your grade"
                : `${
                    answer?.points_awarded !== null && answer?.points_awarded !== undefined
                      ? formatPoints(answer.points_awarded)
                      : "0"
                  } / ${formatPoints(question.points)} points`}
            </p>
            {pending ? (
              <ManualGradeForm
                quizId={quiz.id}
                attemptId={attempt.id}
                question={question}
                disabled={readOnly}
                onSaved={() => onAnnounced("Points saved.")}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export function QuizResultsTable({ quiz, readOnly }: { quiz: TeacherQuiz; readOnly: boolean }) {
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const query = useQuizResultsPage(quiz.id, offset);
  const data = query.data;

  return (
    <section aria-labelledby="results-title" className="space-y-3">
      <Announcer message={status} />
      <h2 id="results-title" className="text-xl font-semibold">
        Results
      </h2>

      {data ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Submitted", String(data.submitted_count)],
            ["Not attempted", String(data.not_attempted_count)],
            ["Attempts", String(data.attempt_count)],
            [
              "Average (best attempts)",
              data.average_score === null
                ? "—"
                : `${formatPoints(data.average_score)} / ${formatPoints(data.max_score)}`,
            ],
          ].map(([term, value]) => (
            <div key={term} className="rounded-lg border p-3">
              <dt className="text-xs text-muted-foreground">{term}</dt>
              <dd className="text-lg font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={data?.attempts.length === 0 && offset === 0}
        emptyText="Nobody has started this quiz yet."
        loadingLabel="Loading results…"
      >
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Attempts and scores for {quiz.title}</caption>
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">
                  Student
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Started
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  Status
                </th>
                <th scope="col" className="px-4 py-2 text-right font-medium">
                  Score
                </th>
                <th scope="col" className="px-4 py-2 font-medium">
                  <span className="sr-only">Review</span>
                </th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data?.attempts.map((attempt) => {
                const name = attempt.student?.full_name ?? "Unknown student";
                const expanded = openId === attempt.id;
                return (
                  <Fragment key={attempt.id}>
                    <tr>
                      <th scope="row" className="px-4 py-3 font-medium">
                        {name}
                      </th>
                      <td className="whitespace-nowrap px-4 py-3">
                        <time dateTime={attempt.started_at}>{formatDateTime(attempt.started_at)}</time>
                      </td>
                      <td className="px-4 py-3">
                        {attempt.submitted_at === null ? (
                          <Badge variant="outline">In progress</Badge>
                        ) : attempt.pending_manual_grading ? (
                          <Badge variant="secondary">Needs grading</Badge>
                        ) : (
                          <Badge>Submitted</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        {attempt.score !== null && attempt.max_score !== null
                          ? `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          aria-expanded={expanded}
                          onClick={() => setOpenId(expanded ? null : attempt.id)}
                        >
                          {expanded ? "Hide" : "Review"}
                          <span className="sr-only"> answers of {name}</span>
                        </Button>
                      </td>
                    </tr>
                    {expanded ? (
                      <tr>
                        <td colSpan={5} className="bg-muted/30 px-4 py-4">
                          <AttemptReview
                            quiz={quiz}
                            attempt={attempt}
                            readOnly={readOnly}
                            onAnnounced={setStatus}
                          />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        {data && data.attempt_count > RESULTS_PAGE_SIZE ? (
          <div className="flex items-center justify-between">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - RESULTS_PAGE_SIZE))}
            >
              Previous
            </Button>
            <p className="text-sm text-muted-foreground">
              {offset + 1}–{Math.min(offset + RESULTS_PAGE_SIZE, data.attempt_count)} of {data.attempt_count}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + RESULTS_PAGE_SIZE >= data.attempt_count}
              onClick={() => setOffset(offset + RESULTS_PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
