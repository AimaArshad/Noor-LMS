import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassworkPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Classwork`);
  return (
    <PagePlaceholder
      title="Classwork"
      description="Assignments, quizzes and materials for this class will appear here."
    />
  );
}
