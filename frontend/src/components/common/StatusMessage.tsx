import { cn } from "@/lib/utils";

/**
 * A visible polite live region for the result of an action ("Announcement posted."). It renders
 * even when empty so assistive tech has a region to report changes into; give it `className`
 * with a min height when it sits in a layout that must not jump.
 */
export function StatusMessage({ message, className }: { message?: string | null; className?: string }) {
  return (
    <p role="status" className={cn("text-sm text-muted-foreground", className)}>
      {message ?? ""}
    </p>
  );
}
