import { cn } from "@/lib/utils";

/** A form- or page-level error. `role="alert"` makes screen readers announce it at once. */
export function ErrorAlert({ message, className }: { message: string | null | undefined; className?: string }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className={cn(
        "rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive",
        className,
      )}
    >
      {message}
    </p>
  );
}
