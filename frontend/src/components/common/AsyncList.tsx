import type { ReactNode } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";

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
  if (isPending) return <Spinner label={loadingLabel} />;
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
      <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{emptyText}</p>
    );
  }
  return <>{children}</>;
}
