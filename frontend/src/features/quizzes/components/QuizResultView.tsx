import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AttemptResult, StudentQuiz } from "@/types";

interface QuizResultViewProps {
  quiz: StudentQuiz;
  attempt: AttemptResult;
  onClose: () => void;
}

/** Per-question outcome. The answer key is never shown (the API does not send it). */
export function QuizResultView({ quiz, attempt, onClose }: QuizResultViewProps) {
  const byQuestion = new Map(attempt.answers.map((a) => [a.question_id, a]));
  const hasScore = attempt.score !== null && attempt.max_score !== null;

  return (
    <section aria-labelledby="result-title" className="space-y-6">
      <header className="relative space-y-2 overflow-hidden rounded-xl border bg-card p-5 shadow-sm">
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1.5 bg-brand" />
        <h2 id="result-title" className="text-lg font-semibold">
          Your result: {quiz.title}
        </h2>
        {hasScore ? (
          <p className="text-3xl font-semibold">
            <span className="text-brand">{formatPoints(attempt.score ?? 0)}</span>
            <span className="text-lg font-normal text-muted-foreground">
              {" "}
              / {formatPoints(attempt.max_score ?? 0)}
            </span>
          </p>
        ) : null}
        {attempt.pending_manual_grading ? (
          <p role="note" className="text-sm text-muted-foreground">
            Some answers are waiting for your teacher to grade them. Your score may go up.
          </p>
        ) : null}
        {attempt.submitted_at ? (
          <p className="text-sm text-muted-foreground">
            Submitted <time dateTime={attempt.submitted_at}>{formatDateTime(attempt.submitted_at)}</time>
          </p>
        ) : null}
      </header>

      {attempt.answers.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No answers were recorded for this attempt (it was closed when the time limit ran out).
        </p>
      ) : (
        <ol className="space-y-3">
          {quiz.questions.map((question, i) => {
            const answer = byQuestion.get(question.id);
            const chosen = answer?.selected_option_id
              ? question.options.find((o) => o.id === answer.selected_option_id)?.text
              : answer?.answer_text;
            const state =
              answer?.is_correct === true ? "correct" : answer?.is_correct === false ? "incorrect" : "pending";
            return (
              <li key={question.id} className="space-y-2 rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium">
                    <span className="text-muted-foreground">{i + 1}. </span>
                    {question.prompt}
                  </p>
                  <p className="flex items-center gap-1 whitespace-nowrap text-sm">
                    {state === "correct" ? (
                      <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
                    ) : state === "incorrect" ? (
                      <XCircle className="h-4 w-4 text-destructive" aria-hidden="true" />
                    ) : (
                      <CircleHelp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    )}
                    <span>
                      {state === "correct" ? "Correct" : state === "incorrect" ? "Incorrect" : "Awaiting grading"}
                      {" · "}
                      {answer?.points_awarded !== null && answer?.points_awarded !== undefined
                        ? formatPoints(answer.points_awarded)
                        : "—"}
                      {" / "}
                      {formatPoints(question.points)}
                    </span>
                  </p>
                </div>
                <p className="text-sm">
                  <span className="text-muted-foreground">Your answer: </span>
                  {chosen ? (
                    <span className="whitespace-pre-wrap break-words">{chosen}</span>
                  ) : (
                    <span className="italic">No answer</span>
                  )}
                </p>
              </li>
            );
          })}
        </ol>
      )}

      <Button type="button" variant="outline" onClick={onClose}>
        Done
      </Button>
    </section>
  );
}
