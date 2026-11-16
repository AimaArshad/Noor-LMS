import { useEffect, useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { filesApi } from "@/features/files/api";

interface BlobUrlState {
  url: string | null;
  loading: boolean;
  error: string | null;
}

/** Fetches a file with the bearer token and exposes an object URL (revoked on cleanup). */
export function useFileBlobUrl(fileId: string, enabled: boolean): BlobUrlState {
  const [state, setState] = useState<BlobUrlState>({ url: null, loading: enabled, error: null });

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setState({ url: null, loading: true, error: null });
    filesApi
      .blob(fileId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setState({ url: null, loading: false, error: getErrorMessage(err, "Could not load the file.") });
        }
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, enabled]);

  return state;
}
