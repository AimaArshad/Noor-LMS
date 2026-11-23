import { Link } from "react-router-dom";

import { useClassroomContext } from "@/features/classrooms/context";
import { QuizBuilder } from "@/features/quizzes/components/QuizBuilder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function QuizBuilderPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`New quiz · ${classroom.name}`);

  if (classroom.my_role !== "teacher" || classroom.is_archived) {
    return (
      <div role="alert" className="space-y-2 py-6">
        <h2 className="text-xl font-semibold">You cannot create quizzes here</h2>
        <p className="text-muted-foreground">
          {classroom.is_archived
            ? "This class is archived and read-only."
            : "Only teachers of this class can create quizzes."}
        </p>
        <Link to={`/classes/${classroom.id}/classwork`} className="text-primary underline underline-offset-4">
          Back to classwork
        </Link>
      </div>
    );
  }
  return <QuizBuilder classroom={classroom} />;
}
