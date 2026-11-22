/**
 * useSpeechRecognition.ts
 * Microphone input → transcript string.
 *
 * Strategy:
 *   1. Use the native SpeechRecognition / webkitSpeechRecognition API (Chrome/Edge).
 *   2. If that is unavailable, record with MediaRecorder and POST to
 *      /api/v1/voice/transcribe (faster-whisper on the backend).
 *
 * Returns reactive state: { transcript, listening, error } and imperative { start, stop }.
 */

import { useCallback, useRef, useState } from "react";

import { transcribeBlob } from "@/voice/voiceClient";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface SpeechRecognitionState {
  transcript: string;
  listening: boolean;
  error: string | null;
  start: () => void;
  stop: () => void;
}

// ---------------------------------------------------------------------------
// Types for the Web Speech API (not all environments expose these in lib.dom.d.ts)
// ---------------------------------------------------------------------------

/** Minimal constructor interface for SpeechRecognition and webkitSpeechRecognition. */
interface SpeechRecognitionConstructor {
  new (): SpeechRecognitionInstance;
}

interface SpeechRecognitionInstance {
  lang: string;
  continuous: boolean;
  interimResults: boolean;
  maxAlternatives: number;
  onstart: (() => void) | null;
  onresult: ((event: SpeechRecognitionResultEvent) => void) | null;
  onerror: ((event: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
}

interface SpeechRecognitionResultEvent {
  results: SpeechRecognitionResultList;
}

// Extend Window typings for webkit-prefixed variant
declare global {
  interface Window {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSpeechRecognition(): SpeechRecognitionState {
  const [transcript, setTranscript] = useState("");
  const [listening, setListening] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Refs — stable across renders
  const nativeRef = useRef<SpeechRecognitionInstance | null>(null);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);

  // -------------------------------------------------------------------------
  // MediaRecorder fallback path
  // -------------------------------------------------------------------------

  const startMediaRecorder = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      mediaRecorderRef.current = recorder;
      chunksRef.current = [];

      recorder.ondataavailable = (e: BlobEvent) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      recorder.onstop = () => {
        // Stop all tracks to release microphone
        stream.getTracks().forEach((t) => t.stop());

        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        chunksRef.current = [];

        void (async () => {
          try {
            const result = await transcribeBlob(blob);
            setTranscript(result.text);
          } catch (err) {
            setError(err instanceof Error ? err.message : "Transcription failed");
          } finally {
            setListening(false);
          }
        })();
      };

      recorder.start();
      setListening(true);
      setError(null);
      setTranscript("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Microphone access denied");
      setListening(false);
    }
  }, []);

  const stopMediaRecorder = useCallback(() => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state !== "inactive") {
      mediaRecorderRef.current.stop();
      // listening → false is set in recorder.onstop (after transcription returns)
    }
  }, []);

  // -------------------------------------------------------------------------
  // SpeechRecognition (native) path
  // -------------------------------------------------------------------------

  const startNative = useCallback(() => {
    const SR =
      (typeof window !== "undefined" && window.SpeechRecognition) ||
      (typeof window !== "undefined" && window.webkitSpeechRecognition);
    if (!SR) return false;

    const rec = new SR();
    nativeRef.current = rec;
    rec.lang = "en-US";
    rec.continuous = false;
    rec.interimResults = false;
    rec.maxAlternatives = 1;

    rec.onstart = () => {
      setListening(true);
      setError(null);
      setTranscript("");
    };

    rec.onresult = (event: SpeechRecognitionResultEvent) => {
      const result = event.results[0]?.[0]?.transcript ?? "";
      setTranscript(result);
    };

    rec.onerror = (event: { error: string }) => {
      setError(event.error);
      setListening(false);
    };

    rec.onend = () => {
      setListening(false);
    };

    try {
      rec.start();
      return true;
    } catch {
      nativeRef.current = null;
      return false;
    }
  }, []);

  const stopNative = useCallback(() => {
    if (nativeRef.current) {
      try {
        nativeRef.current.stop();
      } catch {
        /* ignore */
      }
      nativeRef.current = null;
    }
    setListening(false);
  }, []);

  // -------------------------------------------------------------------------
  // Public API
  // -------------------------------------------------------------------------

  const start = useCallback(() => {
    if (listening) return; // already recording

    const hasNative =
      (typeof window !== "undefined" && Boolean(window.SpeechRecognition)) ||
      (typeof window !== "undefined" && Boolean(window.webkitSpeechRecognition));

    if (hasNative) {
      startNative();
    } else {
      void startMediaRecorder();
    }
  }, [listening, startNative, startMediaRecorder]);

  const stop = useCallback(() => {
    if (nativeRef.current) {
      stopNative();
    } else {
      stopMediaRecorder();
    }
  }, [stopNative, stopMediaRecorder]);

  return { transcript, listening, error, start, stop };
}
