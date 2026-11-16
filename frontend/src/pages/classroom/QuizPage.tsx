import { Link, useParams } from "react-router-dom";

import { getStatus } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";
import { useClassroomContext } from "@/features/classrooms/context";
import { StudentQuizView } from "@/features/quizzes/components/StudentQuizView";
import { TeacherQuizView } from "@/features/quizzes/components/TeacherQuizView";
import { useQuiz } from "@/features/quizzes/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function QuizPage() {
  const { classroom } = useClassroomContext();
  const { quizId = "" } = useParams();
  const { data: quiz, isPending, error, refetch } = useQuiz(quizId);
  useDocumentTitle(quiz ? `${quiz.title} · ${classroom.name}` : classroom.name);

  if (isPending) return <Spinner label="Loading quiz…" />;

  if (error || !quiz || quiz.classroom_id !== classroom.id) {
    const missing = !error || getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="space-y-3 py-6">
        <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to classwork
        </Link>
        <h2 className="text-xl font-semibold">{missing ? "Quiz not found" : "Could not load this quiz"}</h2>
        {!missing ? (
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Try again
          </Button>
        ) : null}
      </div>
    );
  }

  return quiz.view === "teacher" ? (
    <TeacherQuizView quiz={quiz} classroom={classroom} />
  ) : (
    <StudentQuizView quiz={quiz} classroom={classroom} />
  );
}
