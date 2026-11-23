import { Link } from "react-router-dom";

import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ForbiddenPage() {
  useDocumentTitle("Access denied");
  return (
    <section role="alert" className="py-16 text-center">
      <h1 className="text-2xl font-semibold">403: Access denied</h1>
      <p className="mt-1 text-muted-foreground">Your account does not have permission to view this page.</p>
      <Link to="/" className="mt-4 inline-block text-primary underline underline-offset-4">
        Go home
      </Link>
    </section>
  );
}
