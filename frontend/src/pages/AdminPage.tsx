import { PagePlaceholder } from "@/components/common/PagePlaceholder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Only reachable for global admins (see RoleRoute in routes/index.tsx). */
export function AdminPage() {
  useDocumentTitle("Admin");
  return <PagePlaceholder title="Admin" description="Platform administration will live here." />;
}
