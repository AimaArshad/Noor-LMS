/**
 * VoiceProvider.tsx
 * React context that wires together:
 *  - Accessibility settings (GET/PATCH /api/v1/users/me/accessibility)
 *  - SpeechRecognition (useSpeechRecognition)
 *  - TTS (useSpeak)
 *  - Voice command resolution (sendCommand)
 *  - Command handler registry (onCommand)
 *  - aria-live "polite" region for screen-reader announcements
 *
 * Usage:
 *   <VoiceProvider>…app…</VoiceProvider>
 *
 *   const { listen, onCommand, accessibilityMode, setAccessibilityMode } = useVoice();
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { api } from "@/api/client";
import { sendCommand, type VoiceCommandResponse } from "@/voice/voiceClient";
import { AudiobookVoiceRouter } from "@/features/audiobooks/AudiobookVoiceRouter";
import { resolveNavigation } from "@/features/audiobooks/voiceNavigation";
import { useSpeechRecognition } from "@/voice/useSpeechRecognition";
import { useSpeak } from "@/voice/useSpeak";

// ---------------------------------------------------------------------------
// Accessibility settings (backend schema)
// ---------------------------------------------------------------------------

interface AccessibilitySettings {
  tts_enabled: boolean;
  stt_enabled: boolean;
  high_contrast: boolean;
  large_text: boolean;
  tts_voice: string | null;
  tts_speed: number;
}

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface VoiceContextValue {
  /** True when accessibility mode is active (voice + TTS announcements). */
  accessibilityMode: boolean;
  /** Toggle accessibility mode and persist to backend. */
  setAccessibilityMode: (on: boolean) => void;
  /** Current accessibility settings from the backend. */
  settings: AccessibilitySettings | null;
  /** Trigger one recording cycle (start → command → response). */
  listen: () => void;
  /** Whether the system is currently listening. */
  listening: boolean;
  /**
   * Register a handler for resolved voice commands.
   * Returns an unsubscribe function.
   */
  onCommand: (handler: (cmd: VoiceCommandResponse) => void) => () => void;
  /** Speak text aloud (passes through to useSpeak). */
  speak: (text: string) => void;
  /** Tell the voice system which audiobook is open (used when resolving commands). */
  setActiveAudiobook: (id: string | null) => void;
}

// ---------------------------------------------------------------------------
// Context + hook
// ---------------------------------------------------------------------------

const VoiceContext = createContext<VoiceContextValue | null>(null);

export function useVoice(): VoiceContextValue {
  const ctx = useContext(VoiceContext);
  if (!ctx) throw new Error("useVoice must be used inside <VoiceProvider>");
  return ctx;
}

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface VoiceProviderProps {
  children: React.ReactNode;
  /** Optionally pin the active audiobook for command resolution. */
  audiobookId?: string;
}

export function VoiceProvider({ children, audiobookId }: VoiceProviderProps) {
  // --- Accessibility settings ---
  const [settings, setSettings] = useState<AccessibilitySettings | null>(null);
  const [accessibilityMode, setAccessibilityModeState] = useState(false);
  const [activeAudiobookId, setActiveAudiobookId] = useState<string | null>(null);

  useEffect(() => {
    void api
      .get<AccessibilitySettings>("/users/me/accessibility")
      .then(({ data }) => {
        setSettings(data);
        setAccessibilityModeState(data.stt_enabled);
      })
      .catch(() => {
        /* unauthenticated or no row yet — defaults apply */
      });
  }, []);

  const setAccessibilityMode = useCallback(
    (on: boolean) => {
      setAccessibilityModeState(on);
      void api
        .patch<AccessibilitySettings>("/users/me/accessibility", { stt_enabled: on })
        .then(({ data }) => setSettings(data))
        .catch(() => {
          /* best-effort: local state already updated */
        });
    },
    [],
  );

  // --- TTS ---
  const { speak, stop: stopSpeak } = useSpeak();

  // aria-live region ref
  const liveRef = useRef<HTMLDivElement | null>(null);

  const announce = useCallback((text: string) => {
    // Speak aloud
    speak(text);
    // Also put in aria-live region
    if (liveRef.current) {
      liveRef.current.textContent = "";
      // Trigger re-render of the live region by toggling content
      requestAnimationFrame(() => {
        if (liveRef.current) liveRef.current.textContent = text;
      });
    }
  }, [speak]);

  // --- Command handlers ---
  const handlersRef = useRef<Set<(cmd: VoiceCommandResponse) => void>>(new Set());

  const onCommand = useCallback((handler: (cmd: VoiceCommandResponse) => void) => {
    handlersRef.current.add(handler);
    return () => {
      handlersRef.current.delete(handler);
    };
  }, []);

  // --- Speech recognition ---
  const { transcript, listening, start: startRecognition } = useSpeechRecognition();
  const lastTranscriptRef = useRef("");

  // When we get a new transcript, resolve the command
  useEffect(() => {
    if (!transcript || transcript === lastTranscriptRef.current) return;
    lastTranscriptRef.current = transcript;

    void (async () => {
      try {
        // Local voice navigation first (home, classes, audiobooks, play <book>), then the backend.
        const cmd =
          (await resolveNavigation(transcript)) ??
          (await sendCommand(transcript, audiobookId ?? activeAudiobookId ?? undefined));
        // Always announce the speech sentence
        announce(cmd.speech);
        // Notify all registered handlers
        handlersRef.current.forEach((h) => h(cmd));
      } catch {
        announce("Sorry, I could not process that command.");
      }
    })();
  }, [transcript, audiobookId, activeAudiobookId, announce]);

  // --- listen() ---
  const listen = useCallback(() => {
    stopSpeak();
    startRecognition();
  }, [stopSpeak, startRecognition]);

  // --- Accessibility mode announcement on first enable ---
  const prevA11yRef = useRef(accessibilityMode);
  useEffect(() => {
    if (accessibilityMode && !prevA11yRef.current) {
      announce("Voice control on. Press V to speak.");
    }
    prevA11yRef.current = accessibilityMode;
  }, [accessibilityMode, announce]);

  // --- Context value ---
  const value = useMemo<VoiceContextValue>(
    () => ({
      accessibilityMode,
      setAccessibilityMode,
      settings,
      listen,
      listening,
      onCommand,
      speak: announce,
      setActiveAudiobook: setActiveAudiobookId,
    }),
    [accessibilityMode, setAccessibilityMode, settings, listen, listening, onCommand, announce],
  );

  return (
    <VoiceContext.Provider value={value}>
      {/* visually hidden aria-live region — always in the DOM */}
      <div
        ref={liveRef}
        role="status"
        aria-live="polite"
        aria-atomic="true"
        style={{
          position: "absolute",
          width: "1px",
          height: "1px",
          padding: 0,
          margin: "-1px",
          overflow: "hidden",
          clip: "rect(0,0,0,0)",
          whiteSpace: "nowrap",
          border: 0,
        }}
      />
      <AudiobookVoiceRouter onCommand={onCommand} />
      {children}
    </VoiceContext.Provider>
  );
}

