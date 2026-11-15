import { useEffect } from "react";

/** Sets `document.title`. Screen readers announce it on every navigation. */
export function useDocumentTitle(title?: string | null): void {
  useEffect(() => {
    document.title = title ? `${title} · Noor LMS` : "Noor LMS";
  }, [title]);
}
