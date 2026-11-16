import { AssignmentsSection } from "@/features/assignments/components/AssignmentsSection";
import { useClassroomContext } from "@/features/classrooms/context";
import { MaterialsSection } from "@/features/materials/components/MaterialsSection";
import { QuizzesSection } from "@/features/quizzes/components/QuizzesSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassworkPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Classwork`);

  return (
    <div className="space-y-10">
      <AssignmentsSection classroom={classroom} />
      <QuizzesSection classroom={classroom} />
      <MaterialsSection classroom={classroom} />
    </div>
  );
}
