import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function StreamPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Stream`);
  return (
    <PagePlaceholder
      title="Stream"
      description="Announcements and comments for this class will appear here (STEP 8 endpoints)."
    />
  );
}
