/**
 * usePlayer — one <audio> element that plays an audiobook's segments one
 * after another, with a 30 s skip that crosses segment boundaries, speed
 * control, chapter navigation, progress saving and voice-command handling.
 *
 * Segment MP3s need the auth header, so each one is fetched through the api
 * client as a Blob and played from an object URL. The next segment is
 * preloaded while the current one plays.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { playerApi, type AudiobookManifest, type SectionNode, type SegmentInfo } from "./playerApi";
import {
  SPEEDS,
  adjacentChapterSeq,
  buildOutline,
  buildTimeline,
  chapterIndexForSeq,
  commandToAction,
  isReady,
  locate,
} from "./playerLogic";

/** Gap so the spoken reply of a voice command is not played over by the audio. */
const SPEECH_GAP_MS = 1800;
const WAIT_POLL_MS = 5_000;
const WAIT_MAX_TRIES = 120; // ~10 minutes
const SAVE_EVERY_MS = 10_000;

const sortSegments = (m?: AudiobookManifest): SegmentInfo[] =>
  m ? [...m.segments].sort((a, b) => a.seq - b.seq) : [];

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

interface Options {
  audiobookId: string;
  manifest: AudiobookManifest | undefined;
  refetchManifest: () => Promise<AudiobookManifest | undefined>;
  /** Speak a message (only does something when accessibility mode is on). */
  say: (text: string) => void;
}

export function usePlayer({ audiobookId, manifest, refetchManifest, say }: Options) {
  const segments = useMemo(() => sortSegments(manifest), [manifest]);
  const timeline = useMemo(() => buildTimeline(segments), [segments]);
  const chapters = useMemo(() => buildOutline(manifest?.sections ?? []), [manifest]);

  const [index, setIndex] = useState(0);
  const [positionMs, setPositionMs] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [waiting, setWaiting] = useState(false);
  const [rate, setRateState] = useState(1);
  const [message, setMessage] = useState("");
  const [ready, setReady] = useState(false);

  // --- refs (latest values for callbacks / event handlers) -------------------
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const segmentsRef = useRef<SegmentInfo[]>(segments);
  const timelineRef = useRef(timeline);
  const chaptersRef = useRef(chapters);
  const sectionsRef = useRef<SectionNode[]>([]);
  const sayRef = useRef(say);
  const refetchRef = useRef(refetchManifest);

  const idxRef = useRef(0);
  const posRef = useRef(0);
  const playingRef = useRef(false);
  const rateRef = useRef(1);
  const loadedSeqRef = useRef<number | null>(null);
  const loadingRef = useRef(false);
  const tokenRef = useRef(0);
  const cacheRef = useRef(new Map<number, string>());
  const inflightRef = useRef(new Map<number, Promise<string>>());
  const metaHandlerRef = useRef<(() => void) | null>(null);
  const resumeAfterListenRef = useRef(false);
  const cmdTimerRef = useRef<number | undefined>(undefined);
  const initRef = useRef(false);
  const loadRef = useRef<(idx: number, off: number, autoplay: boolean) => Promise<void>>(
    async () => undefined,
  );
  const saveRef = useRef<() => void>(() => undefined);

  const setPlayingBoth = useCallback((v: boolean) => {
    playingRef.current = v;
    setPlaying(v);
  }, []);

  // --- helpers ---------------------------------------------------------------
  const fetchUrl = useCallback(
    (seq: number): Promise<string> => {
      const cached = cacheRef.current.get(seq);
      if (cached) return Promise.resolve(cached);
      const running = inflightRef.current.get(seq);
      if (running) return running;
      const p = playerApi
        .segmentAudio(audiobookId, seq)
        .then((blob) => {
          const url = URL.createObjectURL(blob);
          cacheRef.current.set(seq, url);
          return url;
        })
        .finally(() => {
          inflightRef.current.delete(seq);
        });
      inflightRef.current.set(seq, p);
      return p;
    },
    [audiobookId],
  );

  const trimCache = useCallback((keep: number[]) => {
    for (const [seq, url] of cacheRef.current) {
      if (!keep.includes(seq)) {
        URL.revokeObjectURL(url);
        cacheRef.current.delete(seq);
      }
    }
  }, []);

  /** Poll the manifest until segment `idx` is ready (segments finish progressively). */
  const waitUntilReady = useCallback(async (idx: number, token: number): Promise<boolean> => {
    for (let i = 0; i < WAIT_MAX_TRIES; i++) {
      await sleep(WAIT_POLL_MS);
      if (token !== tokenRef.current) return false;
      try {
        const m = await refetchRef.current();
        if (m) {
          segmentsRef.current = sortSegments(m);
          if (m.status === "failed") return false;
        }
      } catch {
        /* keep trying */
      }
      const s = segmentsRef.current[idx];
      if (s && isReady(s)) return true;
    }
    return false;
  }, []);

  const currentMs = useCallback((): number => {
    const audio = audioRef.current;
    const seg = segmentsRef.current[idxRef.current];
    if (audio && seg && loadedSeqRef.current === seg.seq) return audio.currentTime * 1000;
    return posRef.current;
  }, []);

  // --- loading a segment -----------------------------------------------------
  const loadSegment = useCallback(
    async (idx: number, offsetMs: number, autoplay: boolean) => {
      const audio = audioRef.current;
      const seg = segmentsRef.current[idx];
      if (!audio || !seg) return;

      const token = ++tokenRef.current;
      loadingRef.current = true;
      loadedSeqRef.current = null;
      idxRef.current = idx;
      posRef.current = offsetMs;
      setIndex(idx);
      setPositionMs(offsetMs);
      audio.pause();

      if (!isReady(seg)) {
        const msg = "This part is still being prepared. Please wait.";
        setWaiting(true);
        setMessage(msg);
        sayRef.current(msg);
        const ok = await waitUntilReady(idx, token);
        if (token !== tokenRef.current) return;
        setWaiting(false);
        if (!ok) {
          loadingRef.current = false;
          setMessage("This part could not be prepared.");
          setPlayingBoth(false);
          return;
        }
      }

      let url: string;
      try {
        url = await fetchUrl(segmentsRef.current[idx].seq);
      } catch {
        if (token !== tokenRef.current) return;
        loadingRef.current = false;
        setMessage("Could not load the audio. Please try again.");
        sayRef.current("Could not load the audio.");
        setPlayingBoth(false);
        return;
      }
      if (token !== tokenRef.current) return;

      if (metaHandlerRef.current) {
        audio.removeEventListener("loadedmetadata", metaHandlerRef.current);
      }
      const onMeta = () => {
        audio.removeEventListener("loadedmetadata", onMeta);
        metaHandlerRef.current = null;
        if (token !== tokenRef.current) return;
        audio.playbackRate = rateRef.current;
        audio.currentTime = offsetMs / 1000;
        loadedSeqRef.current = seg.seq;
        loadingRef.current = false;
        setMessage("");
        if (autoplay) {
          audio
            .play()
            .then(() => setPlayingBoth(true))
            .catch(() => {
              setPlayingBoth(false);
              setMessage("Press play to start.");
            });
        }
        // preload the next segment, drop the rest from memory
        const next = segmentsRef.current[idx + 1];
        trimCache([seg.seq, next?.seq ?? -1]);
        if (next && isReady(next)) void fetchUrl(next.seq).catch(() => undefined);
      };
      metaHandlerRef.current = onMeta;
      audio.addEventListener("loadedmetadata", onMeta);
      audio.defaultPlaybackRate = rateRef.current;
      audio.src = url;
    },
    [fetchUrl, trimCache, waitUntilReady, setPlayingBoth],
  );

  // --- progress --------------------------------------------------------------
  const save = useCallback(() => {
    const seg = segmentsRef.current[idxRef.current];
    if (!seg) return;
    void playerApi
      .saveProgress(audiobookId, {
        segment_seq: seg.seq,
        offset_ms: Math.max(0, Math.round(currentMs())),
      })
      .catch(() => undefined);
  }, [audiobookId, currentMs]);

  // --- public controls -------------------------------------------------------
  const play = useCallback(() => {
    resumeAfterListenRef.current = false;
    const audio = audioRef.current;
    const seg = segmentsRef.current[idxRef.current];
    if (!audio || !seg) return;
    if (loadedSeqRef.current === seg.seq) {
      audio
        .play()
        .then(() => setPlayingBoth(true))
        .catch(() => {
          setPlayingBoth(false);
          setMessage("Press play to start.");
        });
    } else {
      void loadRef.current(idxRef.current, posRef.current, true);
    }
  }, [setPlayingBoth]);

  const pause = useCallback(() => {
    resumeAfterListenRef.current = false;
    tokenRef.current++; // cancels any pending load / wait
    loadingRef.current = false;
    setWaiting(false);
    audioRef.current?.pause();
    setPlayingBoth(false);
    saveRef.current();
  }, [setPlayingBoth]);

  const toggle = useCallback(() => {
    if (playingRef.current || loadingRef.current) pause();
    else play();
  }, [pause, play]);

  const goTo = useCallback(
    (idx: number, offsetMs: number, autoplay: boolean) => {
      const seg = segmentsRef.current[idx];
      const audio = audioRef.current;
      if (!seg || !audio) return;
      if (idx === idxRef.current && loadedSeqRef.current === seg.seq) {
        audio.currentTime = offsetMs / 1000;
        posRef.current = offsetMs;
        setPositionMs(offsetMs);
        if (autoplay) play();
        return;
      }
      void loadRef.current(idx, offsetMs, autoplay);
    },
    [play],
  );

  const goToSeq = useCallback(
    (seq: number, autoplay: boolean) => {
      const i = segmentsRef.current.findIndex((s) => s.seq === seq);
      if (i >= 0) goTo(i, 0, autoplay);
    },
    [goTo],
  );

  /** Skip forwards/backwards across segment boundaries. */
  const seekBy = useCallback(
    (deltaMs: number, autoplay?: boolean) => {
      const tl = timelineRef.current;
      const globalMs = (tl.offsets[idxRef.current] ?? 0) + currentMs() + deltaMs;
      const target = locate(tl, globalMs);
      goTo(target.index, target.offsetMs, autoplay ?? playingRef.current);
    },
    [currentMs, goTo],
  );

  const changeChapter = useCallback(
    (dir: 1 | -1, autoplay = true) => {
      const seg = segmentsRef.current[idxRef.current];
      const seq = adjacentChapterSeq(chaptersRef.current, seg?.seq ?? 0, dir);
      if (seq == null) {
        const m = dir > 0 ? "This is the last chapter." : "This is the first chapter.";
        setMessage(m);
        sayRef.current(m);
        return;
      }
      goToSeq(seq, autoplay);
    },
    [goToSeq],
  );

  const changeRate = useCallback((dir: 1 | -1) => {
    const cur = SPEEDS.findIndex((s) => s === rateRef.current);
    const next = Math.max(0, Math.min(SPEEDS.length - 1, (cur < 0 ? 1 : cur) + dir));
    const r = SPEEDS[next];
    rateRef.current = r;
    setRateState(r);
    const audio = audioRef.current;
    if (audio) {
      audio.defaultPlaybackRate = r;
      audio.playbackRate = r;
    }
    setMessage(`Speed ${r}x`);
  }, []);

  /** Mic opened: stop the audio so the microphone does not hear it. */
  const pauseForListening = useCallback(() => {
    if (playingRef.current) {
      resumeAfterListenRef.current = true;
      audioRef.current?.pause();
    }
  }, []);

  /** Apply a resolved voice command ({intent, action, target}). */
  const handleCommand = useCallback(
    (cmd: unknown) => {
      const action = commandToAction(cmd, {
        chapters: chaptersRef.current,
        segments: segmentsRef.current,
        sections: sectionsRef.current,
      });
      if (!action) return;

      const wasPlaying = playingRef.current || resumeAfterListenRef.current;
      window.clearTimeout(cmdTimerRef.current);

      if (action.type === "pause" || action.type === "stop") {
        pause();
        return;
      }

      audioRef.current?.pause(); // stay quiet while the reply is spoken
      let resume = wasPlaying;
      switch (action.type) {
        case "play":
          resume = true;
          break;
        case "seek":
          seekBy(action.deltaMs, false);
          break;
        case "rate":
          changeRate(action.dir);
          break;
        case "chapter":
          changeChapter(action.dir, false);
          resume = true;
          break;
        case "goto":
          goToSeq(action.seq, false);
          resume = true;
          break;
      }
      resumeAfterListenRef.current = false;
      if (resume) cmdTimerRef.current = window.setTimeout(() => play(), SPEECH_GAP_MS);
    },
    [changeChapter, changeRate, goToSeq, pause, play, seekBy],
  );

  // --- effects ---------------------------------------------------------------
  // Create the audio element once.
  useEffect(() => {
    const audio = new Audio();
    audio.preload = "auto";
    audioRef.current = audio;
    const cache = cacheRef.current;

    const onTime = () => {
      if (loadedSeqRef.current === null) return;
      posRef.current = audio.currentTime * 1000;
      setPositionMs(posRef.current);
    };
    const onEnded = () => {
      const next = idxRef.current + 1;
      if (next < segmentsRef.current.length) {
        void loadRef.current(next, 0, true);
      } else {
        setPlayingBoth(false);
        setMessage("End of audiobook.");
        sayRef.current("End of audiobook.");
        saveRef.current();
      }
    };
    const onPlay = () => setPlayingBoth(true);
    const onPause = () => {
      if (!loadingRef.current && !audio.ended) setPlayingBoth(false);
    };
    audio.addEventListener("timeupdate", onTime);
    audio.addEventListener("ended", onEnded);
    audio.addEventListener("play", onPlay);
    audio.addEventListener("pause", onPause);

    return () => {
      saveRef.current();
      tokenRef.current++;
      window.clearTimeout(cmdTimerRef.current);
      audio.removeEventListener("timeupdate", onTime);
      audio.removeEventListener("ended", onEnded);
      audio.removeEventListener("play", onPlay);
      audio.removeEventListener("pause", onPause);
      audio.pause();
      audio.removeAttribute("src");
      audioRef.current = null;
      for (const url of cache.values()) URL.revokeObjectURL(url);
      cache.clear();
    };
  }, [setPlayingBoth]);

  // Keep refs in step with the latest render.
  useEffect(() => {
    segmentsRef.current = segments;
    timelineRef.current = timeline;
    chaptersRef.current = chapters;
    sectionsRef.current = manifest?.sections ?? [];
    sayRef.current = say;
    refetchRef.current = refetchManifest;
    loadRef.current = loadSegment;
    saveRef.current = save;
  });

  // First load: resume where the student stopped.
  useEffect(() => {
    if (!manifest || initRef.current || segments.length === 0) return;
    initRef.current = true;
    const p = manifest.progress;
    let idx = 0;
    let off = 0;
    if (p) {
      const i = segments.findIndex((s) => s.seq === p.segment_seq);
      if (i >= 0) {
        idx = i;
        off = p.offset_ms;
      }
    }
    if (isReady(segments[idx])) {
      void loadRef.current(idx, off, false);
    } else {
      idxRef.current = idx;
      posRef.current = off;
      setIndex(idx);
      setPositionMs(off);
    }
    setReady(true);
  }, [manifest, segments]);

  // Save every 10 s while playing.
  useEffect(() => {
    if (!playing) return;
    const t = window.setInterval(() => saveRef.current(), SAVE_EVERY_MS);
    return () => window.clearInterval(t);
  }, [playing]);

  const currentSegment = segments[index];
  const currentChapterIndex = chapterIndexForSeq(chapters, currentSegment?.seq ?? -1);

  return {
    segments,
    timeline,
    chapters,
    index,
    positionMs,
    globalMs: (timeline.offsets[index] ?? 0) + positionMs,
    currentSegment,
    currentChapterIndex,
    playing,
    waiting,
    rate,
    message,
    ready,
    play,
    pause,
    toggle,
    seekBy,
    changeChapter,
    changeRate,
    goToSeq,
    handleCommand,
    pauseForListening,
  };
}
