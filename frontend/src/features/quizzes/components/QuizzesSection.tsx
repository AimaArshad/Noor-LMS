import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { AsyncList } from "@/components/common/AsyncList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, QuizSummary } from "@/types";

function QuizItem({ quiz, classroomId }: { quiz: QuizSummary; classroomId: string }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">
              <Link
                to={`/classes/${classroomId}/quizzes/${quiz.id}`}
                className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {quiz.title}
              </Link>
            </h3>
            <p className="text-sm text-muted-foreground">
              {quiz.due_at ? (
                <>
                  Due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time>
                </>
              ) : (
                "No due date"
              )}
              {" · "}
              {quiz.time_limit_minutes ? `${quiz.time_limit_minutes} min` : "Untimed"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!quiz.published ? <Badge variant="outline">Draft</Badge> : null}
            {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
          </div>
        </div>
        {quiz.description ? (
          <p className="line-clamp-2 whitespace-pre-wrap break-words text-sm">{quiz.description}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function QuizzesSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useQuizzes(classroom.id);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="quizzes-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="quizzes-title" className="text-xl font-semibold">
          Quizzes
        </h2>
        {canCreate ? (
          <Button asChild>
            <Link to={`/classes/${classroom.id}/quizzes/new`}>
              <Plus aria-hidden="true" />
              Create quiz
            </Link>
          </Button>
        ) : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No quizzes yet."
        loadingLabel="Loading quizzes…"
      >
        <ul className="space-y-3">
          {data?.items.map((quiz) => (
            <li key={quiz.id}>
              <QuizItem quiz={quiz} classroomId={classroom.id} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
