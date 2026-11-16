import { useCallback, useEffect, useRef, useState } from "react";

/** Copies text; `copied` is true for `resetMs` afterwards. Works on plain http via a fallback. */
export function useCopyToClipboard(resetMs = 4000) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      let ok = false;
      if (navigator.clipboard && window.isSecureContext) {
        try {
          await navigator.clipboard.writeText(text);
          ok = true;
        } catch {
          // Permission denied (iframe/permissions policy): fall through to the legacy path.
        }
      }
      if (!ok) {
        try {
          // The Clipboard API is unavailable on plain http (LAN previews) and in some browsers.
          const area = document.createElement("textarea");
          area.value = text;
          area.setAttribute("readonly", "");
          area.style.position = "fixed";
          area.style.opacity = "0";
          document.body.appendChild(area);
          area.select();
          ok = document.execCommand("copy");
          document.body.removeChild(area);
        } catch {
          return false;
        }
      }
      if (!ok) return false;
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), resetMs);
      return true;
    },
    [resetMs],
  );

  return { copied, copy };
}
