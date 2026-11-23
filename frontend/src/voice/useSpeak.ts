/**
 * useSpeak.ts
 * Speak text aloud.
 *
 * Primary:  window.speechSynthesis (SpeechSynthesis API, English).
 * Fallback: POST /api/v1/accessibility/tts → MP3 played with an <audio> element.
 *
 * Usage:
 *   const { speak, stop } = useSpeak();
 *   speak("Going to chapter three.");
 */

import { useCallback, useRef } from "react";

import { api } from "@/api/client";

// ---------------------------------------------------------------------------
// Internal helpers (module-scoped singleton audio element for the fallback)
// ---------------------------------------------------------------------------

let _fallbackAudio: HTMLAudioElement | null = null;

function getFallbackAudio(): HTMLAudioElement {
  if (!_fallbackAudio) {
    _fallbackAudio = new Audio();
    _fallbackAudio.setAttribute("aria-hidden", "true");
  }
  return _fallbackAudio;
}

async function speakViaTTS(text: string): Promise<void> {
  const { data, headers } = await api.post<Blob>(
    "/accessibility/tts",
    { text },
    { responseType: "blob" },
  );
  const mimeType = (headers["content-type"] as string | undefined) ?? "audio/mpeg";
  const url = URL.createObjectURL(new Blob([data], { type: mimeType }));
  const audio = getFallbackAudio();
  audio.src = url;
  await audio.play().catch(() => {
    /* ignore autoplay block */
  });
  audio.onended = () => URL.revokeObjectURL(url);
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

interface UseSpeakReturn {
  /** Speak `text` using SpeechSynthesis (or TTS fallback). */
  speak: (text: string) => void;
  /** Cancel any ongoing speech immediately. */
  stop: () => void;
}

export function useSpeak(): UseSpeakReturn {
  // Track whether SpeechSynthesis is currently in use so we can cancel it.
  const synthSpeakingRef = useRef(false);

  const stop = useCallback(() => {
    if (typeof window !== "undefined" && window.speechSynthesis) {
      window.speechSynthesis.cancel();
    }
    if (_fallbackAudio) {
      _fallbackAudio.pause();
      _fallbackAudio.src = "";
    }
    synthSpeakingRef.current = false;
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (!text.trim()) return;

      stop(); // cancel any previous utterance

      // --- Primary: Web Speech API ---
      if (typeof window !== "undefined" && window.speechSynthesis) {
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.lang = "en-US";
        utterance.rate = 1;

        utterance.onstart = () => {
          synthSpeakingRef.current = true;
        };
        utterance.onend = () => {
          synthSpeakingRef.current = false;
        };
        utterance.onerror = (event) => {
          synthSpeakingRef.current = false;
          // stop()/cancel() raises 'canceled'/'interrupted': that is not a failure,
          // so do not replay the old text through the server voice (double voice).
          const err = (event as SpeechSynthesisErrorEvent).error;
          if (err === "canceled" || err === "interrupted") return;
          void speakViaTTS(text);
        };

        window.speechSynthesis.speak(utterance);
        return;
      }

      // --- Fallback: server-side TTS ---
      void speakViaTTS(text);
    },
    [stop],
  );

  return { speak, stop };
}

