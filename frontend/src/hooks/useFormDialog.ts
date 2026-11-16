import { useCallback, useState } from "react";

/**
 * Open/close state for a form dialog. A dialog cannot be closed while its request is in
 * flight, and `onReset` clears the form every time it opens or closes.
 */
export function useFormDialog({ isPending, onReset }: { isPending: boolean; onReset: () => void }) {
  const [open, setOpen] = useState(false);

  const onOpenChange = useCallback(
    (next: boolean) => {
      if (isPending) return;
      onReset();
      setOpen(next);
    },
    [isPending, onReset],
  );
  const close = useCallback(() => {
    onReset();
    setOpen(false);
  }, [onReset]);

  return { open, onOpenChange, close };
}
