import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QuizResultView } from "@/features/quizzes/components/QuizResultView";
import { QuizTaker, type QuizSession } from "@/features/quizzes/components/QuizTaker";
import { useMyAttempt, useStartQuiz } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AttemptResult, Classroom, StudentQuiz } from "@/types";

export function StudentQuizView({ quiz, classroom }: { quiz: StudentQuiz; classroom: Classroom }) {
  const mine = useMyAttempt(quiz.id);
  const start = useStartQuiz(quiz.id);
  const [session, setSession] = useState<QuizSession | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);

  const onSubmitted = useCallback((attempt: AttemptResult) => {
    setSession(null);
    setResult(attempt);
  }, []);
  const onAbort = useCallback(() => {
    setSession(null);
    void mine.refetch();
  }, [mine]);

  if (session) return <QuizTaker session={session} onSubmitted={onSubmitted} onAbort={onAbort} />;
  if (result) return <QuizResultView quiz={quiz} attempt={result} onClose={() => setResult(null)} />;

  const info = mine.data;
  const attempt = info?.attempt ?? null;
  const open = attempt !== null && attempt.submitted_at === null;
  const finished = attempt !== null && attempt.submitted_at !== null;

  function onStart() {
    start.mutate(undefined, {
      onSuccess: ({ attempt: started, serverNow }) =>
        setSession({
          attemptId: started.attempt_id,
          expiresAt: started.expires_at,
          skewMs: serverNow === null ? 0 : serverNow - Date.now(),
          quiz: started.quiz,
        }),
    });
  }

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to classwork
      </Link>

      <header className="space-y-2">
        <h2 className="break-words text-2xl font-semibold tracking-tight">{quiz.title}</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>
            {quiz.questions.length} question{quiz.questions.length === 1 ? "" : "s"}
          </span>
          <span aria-hidden="true">·</span>
          <span>{quiz.time_limit_minutes ? `${quiz.time_limit_minutes} minutes` : "No time limit"}</span>
          {quiz.due_at ? (
            <>
              <span aria-hidden="true">·</span>
              <span>
                Due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time>
              </span>
            </>
          ) : null}
          {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
        </div>
        {quiz.description ? <p className="whitespace-pre-wrap break-words">{quiz.description}</p> : null}
      </header>

      {mine.isPending ? <Spinner label="Loading your attempts…" /> : null}
      {mine.isError ? (
        <div className="space-y-3">
          <ErrorAlert message={getErrorMessage(mine.error)} />
          <Button variant="outline" size="sm" onClick={() => void mine.refetch()}>
            Try again
          </Button>
        </div>
      ) : null}

      {info ? (
        <section aria-label="Your attempts" className="space-y-4 rounded-lg border p-4">
          {finished && attempt ? (
            <div className="space-y-1">
              <p className="font-medium">
                Last attempt:{" "}
                {attempt.score !== null && attempt.max_score !== null
                  ? `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`
                  : "submitted"}
                {attempt.pending_manual_grading ? " (some answers await grading)" : ""}
              </p>
              <Button variant="outline" size="sm" onClick={() => setResult(attempt)}>
                Review last attempt
              </Button>
            </div>
          ) : null}
          {open && quiz.time_limit_minutes ? (
            <p role="note" className="text-sm text-muted-foreground">
              You have an attempt in progress. Its timer keeps running while you are away.
            </p>
          ) : null}
          {!info.can_start && info.attempts_used > 0 && !open ? (
            <p className="text-sm text-muted-foreground">
              {classroom.is_archived
                ? "This class is archived."
                : "You have completed this quiz. Retakes are not allowed."}
            </p>
          ) : null}

          <ErrorAlert message={start.isError ? getErrorMessage(start.error) : null} />
          {info.can_start ? (
            <Button disabled={start.isPending} onClick={onStart}>
              {start.isPending
                ? "Starting…"
                : open
                  ? "Resume quiz"
                  : info.attempts_used > 0
                    ? "Retake quiz"
                    : "Start quiz"}
            </Button>
          ) : null}
          {info.attempts_used > 0 ? (
            <p className="text-xs text-muted-foreground">Attempts used: {info.attempts_used}</p>
          ) : null}
        </section>
      ) : null}
    </article>
  );
}
