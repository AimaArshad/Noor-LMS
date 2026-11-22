import { RefreshCw, Trash2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  BUILDING_STATUSES,
  type AudiobookRead,
  type AudiobookListItem,
  type AudiobookStatus,
} from "@/features/audiobooks/api";
import { useDeleteAudiobook, useRebuildAudiobook } from "@/features/audiobooks/hooks";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Status badge
// ---------------------------------------------------------------------------

const STATUS_STYLES: Record<AudiobookStatus, string> = {
  queued: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/50 dark:text-yellow-300",
  extracting: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  synthesizing: "bg-blue-100 text-blue-800 dark:bg-blue-900/50 dark:text-blue-300",
  ready: "bg-green-100 text-green-800 dark:bg-green-900/50 dark:text-green-300",
  failed: "bg-red-100 text-red-800 dark:bg-red-900/50 dark:text-red-300",
  needs_ocr: "bg-orange-100 text-orange-800 dark:bg-orange-900/50 dark:text-orange-300",
};

const STATUS_LABELS: Record<AudiobookStatus, string> = {
  queued: "Queued",
  extracting: "Extracting",
  synthesizing: "Synthesizing",
  ready: "Ready",
  failed: "Failed",
  needs_ocr: "Needs OCR",
};

function StatusBadge({ status }: { status: AudiobookStatus }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium",
        STATUS_STYLES[status] ?? "bg-muted text-muted-foreground",
      )}
    >
      {STATUS_LABELS[status] ?? status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Progress bar
// ---------------------------------------------------------------------------

function ProgressBar({ pct }: { pct: number }) {
  const clamped = Math.max(0, Math.min(100, Math.round(pct)));
  return (
    <div
      className="h-2 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuenow={clamped}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Build progress: ${clamped}%`}
    >
      <div
        className="h-full rounded-full bg-primary transition-[width] duration-300"
        style={{ width: `${clamped}%` }}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Item card
// ---------------------------------------------------------------------------

type AudiobookItem = AudiobookRead | AudiobookListItem;

interface AudiobookItemCardProps {
  item: AudiobookItem;
  classroomId: string;
  isTeacher: boolean;
  isArchived: boolean;
  onAnnounced: (msg: string | null) => void;
}

export function AudiobookItemCard({
  item,
  classroomId,
  isTeacher,
  isArchived,
  onAnnounced,
}: AudiobookItemCardProps) {
  const rebuild = useRebuildAudiobook(classroomId);
  const remove = useDeleteAudiobook(classroomId);

  const isBuilding = BUILDING_STATUSES.includes(item.status);
  const canManage = isTeacher && !isArchived;

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        {/* Title row */}
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0 flex-1">
            <h3 className="break-words font-medium">{item.title}</h3>
            <div className="mt-1 flex flex-wrap items-center gap-2">
              <StatusBadge status={item.status} />
              {item.page_count != null ? (
                <span className="text-xs text-muted-foreground">
                  {item.page_count} page{item.page_count === 1 ? "" : "s"}
                </span>
              ) : null}
            </div>
          </div>

          {/* Teacher action buttons */}
          {canManage ? (
            <div className="flex shrink-0 gap-1">
              <Button
                type="button"
                variant="outline"
                size="sm"
                disabled={isBuilding || rebuild.isPending}
                aria-label={`Rebuild ${item.title}`}
                onClick={() => {
                  onAnnounced(null);
                  rebuild.mutate(item.id, {
                    onSuccess: () => onAnnounced(`Rebuilding "${item.title}".`),
                    onError: (err) => onAnnounced(`Rebuild failed: ${getErrorMessage(err)}`),
                  });
                }}
              >
                <RefreshCw
                  className={cn("h-4 w-4", rebuild.isPending && "animate-spin")}
                  aria-hidden="true"
                />
                <span className="sr-only sm:not-sr-only sm:ml-1.5">Rebuild</span>
              </Button>

              <ConfirmDialog
                title="Delete this audiobook?"
                description={`"${item.title}" and all its audio will be permanently removed.`}
                onConfirm={() => {
                  onAnnounced(null);
                  remove.mutate(item.id, {
                    onSuccess: () => onAnnounced(`Deleted "${item.title}".`),
                    onError: (err) => onAnnounced(`Delete failed: ${getErrorMessage(err)}`),
                  });
                }}
                trigger={
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    disabled={remove.isPending}
                    aria-label={`Delete ${item.title}`}
                  >
                    <Trash2 className="h-4 w-4" aria-hidden="true" />
                    <span className="sr-only">Delete</span>
                  </Button>
                }
              />
            </div>
          ) : null}
        </div>

        {/* Progress bar — only while building */}
        {isBuilding && item.progress_pct != null ? (
          <ProgressBar pct={item.progress_pct} />
        ) : null}

        {/* Error text */}
        {item.status === "failed" && item.error ? (
          <ErrorAlert message={item.error} />
        ) : null}

        {/* Needs OCR message */}
        {item.status === "needs_ocr" ? (
          <p className="text-sm text-orange-600 dark:text-orange-400">
            This document appears to be scanned (image-only). OCR support will be added soon.
          </p>
        ) : null}

        {/* Mutation errors */}
        <ErrorAlert message={rebuild.isError ? getErrorMessage(rebuild.error) : null} />
        <ErrorAlert message={remove.isError ? getErrorMessage(remove.error) : null} />
      </CardContent>
    </Card>
  );
}
