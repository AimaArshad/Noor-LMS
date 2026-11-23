import { Link } from "react-router-dom";

import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function NotFoundPage() {
  useDocumentTitle("Page not found");
  return (
    <section className="py-16 text-center">
      <h1 className="text-2xl font-semibold">404: Page not found</h1>
      <p className="mt-1 text-muted-foreground">That page does not exist.</p>
      <Link to="/" className="mt-4 inline-block text-primary underline underline-offset-4">
        Go home
      </Link>
    </section>
  );
}
