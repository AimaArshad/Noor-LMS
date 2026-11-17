import { Inbox } from "lucide-react";
import type { ReactNode } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";

interface AsyncListProps {
  isPending: boolean;
  error: unknown;
  onRetry: () => void;
  /** Set to false when a section has more than one list (People: teachers + students). */
  isEmpty?: boolean;
  emptyText?: string;
  loadingLabel?: string;
  children: ReactNode;
}

/** Loading, error (with retry) and empty states in one place; renders `children` otherwise. */
export function AsyncList({
  isPending,
  error,
  onRetry,
  isEmpty = false,
  emptyText = "",
  loadingLabel = "Loading…",
  children,
}: AsyncListProps) {
  if (isPending) {
    return (
      <div role="status" aria-live="polite" className="space-y-3">
        <span className="sr-only">{loadingLabel}</span>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  if (isEmpty) {
    return (
      <div className="rounded-xl border border-dashed bg-card/60 p-8 text-center">
        <Inbox className="mx-auto mb-2 h-6 w-6 text-muted-foreground" aria-hidden="true" />
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      </div>
    );
  }
  return <>{children}</>;
}
