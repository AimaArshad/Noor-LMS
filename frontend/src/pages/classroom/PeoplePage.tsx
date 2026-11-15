import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PeoplePage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · People`);
  return (
    <PagePlaceholder
      title="People"
      description="Teachers and students of this class will appear here (GET /classrooms/{id}/people)."
    />
  );
}
