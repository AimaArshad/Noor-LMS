import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function TodoPage() {
  useDocumentTitle("To-Do");
  return <PagePlaceholder title="To-Do" description="Your pending assignments and quizzes will appear here (GET /todo)." />;
}
