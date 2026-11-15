import { Loader2 } from "lucide-react";

interface SpinnerProps {
  label?: string;
  /** Center in the whole viewport (used while the session is being restored). */
  fullPage?: boolean;
}

export function Spinner({ label = "Loading…", fullPage = false }: SpinnerProps) {
  const content = (
    <div role="status" className="flex items-center justify-center gap-2 text-muted-foreground">
      <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
      <span>{label}</span>
    </div>
  );
  return fullPage ? (
    <div className="flex min-h-screen items-center justify-center">{content}</div>
  ) : (
    <div className="py-10">{content}</div>
  );
}
