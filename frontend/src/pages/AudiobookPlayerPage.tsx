import { FastForward, Pause, Play, Rewind, SkipBack, SkipForward } from "lucide-react";
import { useCallback, useEffect, useRef } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { useVoice } from "@/voice/VoiceProvider";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { BUILDING_STATUSES } from "@/features/audiobooks/api";
import { playerApi } from "@/features/audiobooks/playerApi";
import { SEEK_MS, topicForSeq, wantsAudiobook } from "@/features/audiobooks/playerLogic";
import { usePlayer } from "@/features/audiobooks/usePlayer";
import { cn } from "@/lib/utils";

function fmt(ms: number): string {
  const total = Math.max(0, Math.floor(ms / 1000));
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${String(m).padStart(2, "0")}:${ss}` : `${m}:${ss}`;
}

const pageText = (label: string) => (/^\d/.test(label) ? `Page ${label}` : label);

/** /audiobooks/:audiobookId */
export function AudiobookPlayerPage() {
  const { audiobookId } = useParams<{ audiobookId: string }>();
  if (!audiobookId) return <p role="alert">Audiobook not found.</p>;
  // key: a different book (e.g. opened by voice) starts with a fresh player
  return <PlayerView key={audiobookId} audiobookId={audiobookId} />;
}

function PlayerView({ audiobookId }: { audiobookId: string }) {
  const navigate = useNavigate();
  const location = useLocation();
  const { speak, accessibilityMode, listening, onCommand, setActiveAudiobook } = useVoice();

  const query = useQuery({
    queryKey: ["audiobook", "manifest", audiobookId],
    queryFn: () => playerApi.manifest(audiobookId),
    refetchInterval: (q) => {
      const s = q.state.data?.status;
      return s && (BUILDING_STATUSES as readonly string[]).includes(s) ? 10_000 : false;
    },
  });
  const manifest = query.data;
  const { refetch } = query;
  const refetchManifest = useCallback(async () => (await refetch()).data, [refetch]);

  const say = useCallback(
    (text: string) => {
      if (accessibilityMode) speak(text);
    },
    [accessibilityMode, speak],
  );

  const player = usePlayer({ audiobookId, manifest, refetchManifest, say });
  const { toggle, seekBy, changeChapter, changeRate, handleCommand, pauseForListening } = player;

  // Tell the voice system which book is open so commands resolve against it.
  useEffect(() => {
    setActiveAudiobook(audiobookId);
    return () => setActiveAudiobook(null);
  }, [audiobookId, setActiveAudiobook]);

  // Voice commands.
  useEffect(
    () =>
      onCommand((cmd) => {
        const other = wantsAudiobook(cmd);
        if (other && other !== audiobookId) {
          navigate(`/audiobooks/${other}`, { state: { pendingCommand: cmd } });
          return;
        }
        handleCommand(cmd);
      }),
    [onCommand, audiobookId, navigate, handleCommand],
  );

  // A command that opened this page ("go to chapter 2 in physics").
  const pendingRef = useRef<unknown>(
    (location.state as { pendingCommand?: unknown } | null)?.pendingCommand ?? null,
  );
  useEffect(() => {
    if (player.ready && pendingRef.current) {
      const cmd = pendingRef.current;
      pendingRef.current = null;
      handleCommand(cmd);
    }
  }, [player.ready, handleCommand]);

  // Silence the audio while the microphone is open.
  useEffect(() => {
    if (listening) pauseForListening();
  }, [listening, pauseForListening]);

  // Keyboard: Space, ←/→ 30 s, [ ] speed, N/P chapter.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey) return;
      const el = e.target as HTMLElement | null;
      if (el?.closest("input, textarea, select, [contenteditable='true']")) return;
      switch (e.key) {
        case " ":
          if (el?.closest("button, a")) return; // let the focused control handle it
          e.preventDefault();
          toggle();
          break;
        case "ArrowRight":
          e.preventDefault();
          seekBy(SEEK_MS);
          break;
        case "ArrowLeft":
          e.preventDefault();
          seekBy(-SEEK_MS);
          break;
        case "[":
          changeRate(-1);
          break;
        case "]":
          changeRate(1);
          break;
        case "n":
        case "N":
          changeChapter(1);
          break;
        case "p":
        case "P":
          changeChapter(-1);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [toggle, seekBy, changeChapter, changeRate]);

  // ---- render ---------------------------------------------------------------
  if (query.isLoading) return <p role="status">Loading audiobook…</p>;
  if (query.error || !manifest) {
    return (
      <div className="py-6">
        <ErrorAlert message={query.error ? getErrorMessage(query.error) : "Audiobook not found."} />
      </div>
    );
  }

  const { chapters, currentChapterIndex, currentSegment, globalMs, timeline } = player;
  const chapter = chapters[currentChapterIndex];
  const topic = topicForSeq(chapter, currentSegment?.seq ?? -1);
  const building = (BUILDING_STATUSES as readonly string[]).includes(manifest.status);
  const nowPlaying = chapter
    ? `${chapter.section.title}${topic ? " — " + topic.title : ""}`
    : "Introduction";
  const pct = timeline.total > 0 ? Math.min(100, Math.round((globalMs / timeline.total) * 100)) : 0;

  return (
    <div className="mx-auto max-w-3xl space-y-5 py-6">
      <header className="space-y-1">
        <h1 className="break-words text-2xl font-semibold">{manifest.title}</h1>
        {building ? (
          <p className="text-sm text-muted-foreground">
            Still being prepared ({Math.round(manifest.progress_pct ?? 0)}%). You can listen to the
            finished parts now.
          </p>
        ) : null}
        {manifest.status === "failed" ? <ErrorAlert message={manifest.error ?? "Build failed."} /> : null}
      </header>

      <Card>
        <CardContent className="space-y-4 p-5">
          <div>
            <p className="text-xs uppercase tracking-wide text-muted-foreground">Now playing</p>
            <p className="break-words text-lg font-medium">{nowPlaying}</p>
            {currentSegment ? (
              <p className="text-sm text-muted-foreground">{pageText(currentSegment.page_label)}</p>
            ) : null}
          </div>

          <div
            className="h-2 w-full overflow-hidden rounded-full bg-muted"
            role="progressbar"
            aria-label="Listening progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={pct}
            aria-valuetext={`${fmt(globalMs)} of ${fmt(timeline.total)}`}
          >
            <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
          </div>
          <p className="text-sm tabular-nums text-muted-foreground">
            {fmt(globalMs)} / {fmt(timeline.total)}
          </p>

          <div className="flex flex-wrap items-center justify-center gap-2">
            <Button type="button" variant="outline" onClick={() => changeChapter(-1)} aria-label="Previous chapter (P)">
              <SkipBack className="h-4 w-4" aria-hidden="true" />
            </Button>
            <Button type="button" variant="outline" onClick={() => seekBy(-SEEK_MS)} aria-label="Back 30 seconds (Left arrow)">
              <Rewind className="mr-1 h-4 w-4" aria-hidden="true" />
              30s
            </Button>
            <Button
              type="button"
              size="lg"
              onClick={toggle}
              aria-label={player.playing ? "Pause (Space)" : "Play (Space)"}
              className="min-w-28"
            >
              {player.playing ? (
                <Pause className="mr-1 h-5 w-5" aria-hidden="true" />
              ) : (
                <Play className="mr-1 h-5 w-5" aria-hidden="true" />
              )}
              {player.playing ? "Pause" : "Play"}
            </Button>
            <Button type="button" variant="outline" onClick={() => seekBy(SEEK_MS)} aria-label="Forward 30 seconds (Right arrow)">
              30s
              <FastForward className="ml-1 h-4 w-4" aria-hidden="true" />
            </Button>
            <Button type="button" variant="outline" onClick={() => changeChapter(1)} aria-label="Next chapter (N)">
              <SkipForward className="h-4 w-4" aria-hidden="true" />
            </Button>
          </div>

          <div className="flex items-center justify-center gap-2 text-sm">
            <Button type="button" variant="ghost" size="sm" onClick={() => changeRate(-1)} aria-label="Slower ([)">
              Slower
            </Button>
            <span className="min-w-16 text-center tabular-nums" aria-label={`Speed ${player.rate} times`}>
              {player.rate}x
            </span>
            <Button type="button" variant="ghost" size="sm" onClick={() => changeRate(1)} aria-label="Faster (])">
              Faster
            </Button>
          </div>

          {/* Spoken/visible status: waiting for audio, speed changes, errors */}
          <p role="status" aria-live="polite" className="min-h-5 text-center text-sm text-muted-foreground">
            {player.message}
          </p>
          {/* Announced by screen readers whenever the chapter or topic changes */}
          <p className="sr-only" aria-live="polite">
            {`Now playing: ${nowPlaying}. ${currentSegment ? pageText(currentSegment.page_label) : ""}`}
          </p>
        </CardContent>
      </Card>

      <nav aria-label="Chapters" className="space-y-2">
        <h2 className="text-lg font-semibold">Chapters</h2>
        {chapters.length === 0 ? (
          <p className="text-sm text-muted-foreground">This book has no chapter outline.</p>
        ) : (
          <ol className="space-y-2">
            {chapters.map((c, i) => {
              const current = i === currentChapterIndex;
              const first = c.section.first_segment_seq;
              return (
                <li key={c.section.id}>
                  <details open={current} className="rounded-md border p-2">
                    <summary className="flex cursor-pointer items-center gap-2">
                      <Button
                        type="button"
                        variant={current ? "default" : "outline"}
                        size="sm"
                        disabled={first == null}
                        aria-current={current ? "true" : undefined}
                        onClick={(e) => {
                          e.preventDefault();
                          if (first != null) player.goToSeq(first, true);
                        }}
                      >
                        Play
                      </Button>
                      <span className={cn("break-words", current && "font-semibold")}>
                        {c.section.number != null ? `${c.section.number}. ` : ""}
                        {c.section.title}
                      </span>
                    </summary>
                    {c.topics.length > 0 ? (
                      <ul className="mt-2 space-y-1 pl-4">
                        {c.topics.map((t) => (
                          <li key={t.id}>
                            <button
                              type="button"
                              disabled={t.first_segment_seq == null}
                              onClick={() => t.first_segment_seq != null && player.goToSeq(t.first_segment_seq, true)}
                              className={cn(
                                "rounded px-1 text-left text-sm hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                                topic?.id === t.id && "font-semibold",
                              )}
                            >
                              {t.title}
                            </button>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </details>
                </li>
              );
            })}
          </ol>
        )}
      </nav>

      <p className="text-xs text-muted-foreground">
        Keyboard: Space play/pause · ← → skip 30 seconds · [ ] slower/faster · N / P next/previous
        chapter · V voice.
      </p>
    </div>
  );
}
