import { Play } from "lucide-react";
import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useVoice } from "@/voice/VoiceProvider";
import { Card, CardContent } from "@/components/ui/card";
import { BUILDING_STATUSES } from "@/features/audiobooks/api";
import { playerApi } from "@/features/audiobooks/playerApi";
import { describeLibrary } from "@/features/audiobooks/voiceNavigationLogic";

const STATUS_TEXT: Record<string, string> = {
  queued: "Queued",
  extracting: "Preparing",
  synthesizing: "Being prepared, partly playable",
  ready: "Ready",
  failed: "Failed",
  needs_ocr: "Needs OCR",
};

/** /audiobooks â€” every audiobook the signed-in user can open. */
export function AudiobookLibraryPage() {
  const location = useLocation();
  const { speak } = useVoice();
  const spokenFor = useRef<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["audiobooks", "all"],
    queryFn: playerApi.listAll,
    refetchInterval: (q) => {
      const items = q.state.data;
      return items?.some((i) => (BUILDING_STATUSES as readonly string[]).includes(i.status))
        ? 10_000
        : false;
    },
  });

  // Opened by voice ("open audiobooks"): read the list aloud once.
  useEffect(() => {
    const st = location.state as { announceList?: boolean } | null;
    if (!st?.announceList || !data || spokenFor.current === location.key) return;
    spokenFor.current = location.key;
    speak(describeLibrary(data));
  }, [data, location.key, location.state, speak]);

  return (
    <div className="mx-auto max-w-3xl space-y-4 py-6">
      <h1 className="text-2xl font-semibold">Audiobooks</h1>
      <p className="text-sm text-muted-foreground">
        Choose a book to listen to. With voice control on, say for example â€œplay physics 2nd yearâ€.
      </p>

      <ErrorAlert message={error ? getErrorMessage(error) : null} />
      {isLoading ? <p role="status">Loading audiobooksâ€¦</p> : null}
      {data && data.length === 0 ? <p role="status">No audiobooks yet.</p> : null}

      <ul className="space-y-3" aria-label="Audiobooks">
        {data?.map((ab) => {
          const playable = ab.status === "ready" || ab.status === "synthesizing";
          return (
            <li key={ab.id}>
              <Card>
                <CardContent className="flex items-center justify-between gap-3 p-4">
                  <div className="min-w-0">
                    <h2 className="break-words font-medium">{ab.title}</h2>
                    <p className="text-sm text-muted-foreground">
                      {ab.classroom_name} Â· {STATUS_TEXT[ab.status] ?? ab.status}
                      {ab.page_count != null ? ` Â· ${ab.page_count} pages` : ""}
                    </p>
                  </div>
                  {playable ? (
                    <Link
                      to={`/audiobooks/${ab.id}`}
                      aria-label={`Play ${ab.title}`}
                      className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    >
                      <Play className="h-4 w-4" aria-hidden="true" />
                      Play
                    </Link>
                  ) : null}
                </CardContent>
              </Card>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

