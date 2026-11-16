import { Check } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { Announcer } from "@/components/common/Announcer";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QuizResultsTable } from "@/features/quizzes/components/QuizResultsTable";
import { useUpdateQuiz } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { Classroom, TeacherQuiz } from "@/types";

const TYPE_LABEL = { mcq: "Multiple choice", true_false: "True / False", short_answer: "Short answer" } as const;

export function TeacherQuizView({ quiz, classroom }: { quiz: TeacherQuiz; classroom: Classroom }) {
  const update = useUpdateQuiz(quiz.id);
  const [status, setStatus] = useState("");
  const readOnly = classroom.is_archived;
  const total = quiz.questions.reduce((sum, q) => sum + q.points, 0);

  return (
    <article className="mx-auto max-w-4xl space-y-8">
      <Announcer message={status} />
      <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to classwork
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="break-words text-2xl font-semibold tracking-tight">{quiz.title}</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={quiz.published ? "default" : "outline"}>{quiz.published ? "Published" : "Draft"}</Badge>
            {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
            {!readOnly ? (
              <Button
                size="sm"
                variant={quiz.published ? "outline" : "default"}
                disabled={update.isPending}
                onClick={() =>
                  update.mutate(!quiz.published, {
                    onSuccess: () =>
                      setStatus(quiz.published ? "Quiz unpublished." : "Quiz published. Students can see it now."),
                  })
                }
              >
                {update.isPending ? "Saving…" : quiz.published ? "Unpublish" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {quiz.questions.length} question{quiz.questions.length === 1 ? "" : "s"} · {formatPoints(total)} points ·{" "}
          {quiz.time_limit_minutes ? `${quiz.time_limit_minutes} min` : "untimed"}
          {quiz.due_at ? (
            <>
              {" "}
              · due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time>
            </>
          ) : null}
        </p>
        {quiz.description ? <p className="whitespace-pre-wrap break-words">{quiz.description}</p> : null}
        <ErrorAlert message={update.isError ? getErrorMessage(update.error) : null} />
      </header>

      <section aria-labelledby="questions-title" className="space-y-3">
        <h2 id="questions-title" className="text-xl font-semibold">
          Questions
        </h2>
        {quiz.questions.length === 0 ? (
          <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            This quiz has no questions, so it cannot be published.
          </p>
        ) : (
          <ol className="space-y-3">
            {quiz.questions.map((question, i) => (
              <li key={question.id} className="space-y-2 rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium">
                    <span className="text-muted-foreground">{i + 1}. </span>
                    {question.prompt}
                  </p>
                  <p className="whitespace-nowrap text-sm text-muted-foreground">
                    {TYPE_LABEL[question.type]} · {formatPoints(question.points)} pt
                  </p>
                </div>
                {question.options.length > 0 ? (
                  <ul className="space-y-1 text-sm">
                    {question.options.map((option) => (
                      <li key={option.id} className="flex items-center gap-2">
                        {option.is_correct ? (
                          <>
                            <Check className="h-4 w-4 text-primary" aria-hidden="true" />
                            <span className="sr-only">Correct: </span>
                          </>
                        ) : (
                          <span className="inline-block h-4 w-4" aria-hidden="true" />
                        )}
                        <span className={option.is_correct ? "font-medium" : undefined}>{option.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm italic text-muted-foreground">Graded by hand.</p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      {quiz.published || quiz.questions.length > 0 ? <QuizResultsTable quiz={quiz} readOnly={readOnly} /> : null}
    </article>
  );
}
