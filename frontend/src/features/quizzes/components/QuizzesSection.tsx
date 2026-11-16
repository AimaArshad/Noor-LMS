import { AsyncList } from "@/components/common/AsyncList";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CreateQuizDialog } from "@/features/quizzes/components/CreateQuizDialog";
import { useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, QuizSummary } from "@/types";

function QuizItem({ quiz, isTeacher }: { quiz: QuizSummary; isTeacher: boolean }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{quiz.title}</h3>
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
        {isTeacher && !quiz.published ? (
          <p className="text-xs text-muted-foreground">Draft: add questions before publishing (quiz editor comes next).</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function QuizzesSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useQuizzes(classroom.id);
  const isTeacher = classroom.my_role === "teacher";
  const canCreate = isTeacher && !classroom.is_archived;

  return (
    <section aria-labelledby="quizzes-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="quizzes-title" className="text-xl font-semibold">
          Quizzes
        </h2>
        {canCreate ? <CreateQuizDialog classroomId={classroom.id} /> : null}
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
              <QuizItem quiz={quiz} isTeacher={isTeacher} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
