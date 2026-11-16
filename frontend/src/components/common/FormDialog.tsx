import { useEffect, useRef, type FormEvent, type ReactNode } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

interface FormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: ReactNode;
  title: string;
  description: string;
  submitLabel: string;
  pendingLabel: string;
  isPending: boolean;
  /** The mutation error, if any. */
  error: unknown;
  /**
   * Validate and send. Return `false` when validation failed (the dialog stays open, no request
   * was sent); anything else is treated as "request started".
   */
  onSubmit: () => boolean | void;
  children: ReactNode;
}

export function FormDialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  submitLabel,
  pendingLabel,
  isPending,
  error,
  onSubmit,
  children,
}: FormDialogProps) {
  // `isPending` only disables the button on the next render, so two submit events in the same
  // tick would send two requests. This ref closes that gap and is released when the request ends.
  const inFlight = useRef(false);
  useEffect(() => {
    if (!isPending) inFlight.current = false;
  }, [isPending]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current || isPending) return;
    if (onSubmit() === false) return;
    inFlight.current = true;
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form noValidate onSubmit={handleSubmit} className="space-y-4">
          <ErrorAlert message={error ? getErrorMessage(error) : null} />
          {children}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={isPending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? pendingLabel : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
