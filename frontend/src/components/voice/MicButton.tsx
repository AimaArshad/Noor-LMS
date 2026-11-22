/**
 * MicButton.tsx
 * Fixed bottom-right microphone button.
 *
 * Behaviour:
 *  - Click OR hold/toggle with the V key to push-to-talk (V ignored while typing in inputs).
 *  - aria-pressed reflects listening state.
 *  - Visible focus ring (focus-visible).
 *  - In accessibility mode, V key starts/stops recording.
 */

import { useEffect, useRef } from "react";
import { Mic, MicOff } from "lucide-react";

import { useVoice } from "@/voice/VoiceProvider";
import { cn } from "@/lib/utils";

/** Returns true when the keyboard event originates from a text-entry element. */
function isTypingTarget(el: EventTarget | null): boolean {
  if (!(el instanceof HTMLElement)) return false;
  const tag = el.tagName.toLowerCase();
  if (tag === "input" || tag === "textarea" || tag === "select") return true;
  if (el.isContentEditable) return true;
  return false;
}

export function MicButton() {
  const { listen, listening, accessibilityMode } = useVoice();
  const buttonRef = useRef<HTMLButtonElement>(null);

  // V key — push-to-talk (hold-or-toggle); ignore while typing
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key.toLowerCase() !== "v") return;
      if (e.repeat) return;
      if (isTypingTarget(e.target)) return;

      e.preventDefault();
      listen();
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [listen]);

  const label = listening ? "Stop listening" : "Start voice command (V)";

  return (
    <button
      ref={buttonRef}
      type="button"
      aria-label={label}
      aria-pressed={listening}
      onClick={listen}
      className={cn(
        // Fixed position, bottom-right
        "fixed bottom-6 right-6 z-50",
        // Size & shape
        "flex h-14 w-14 items-center justify-center rounded-full shadow-lg",
        // Focus ring (always visible for keyboard users)
        "focus:outline-none focus-visible:ring-4 focus-visible:ring-ring focus-visible:ring-offset-2",
        // Colour: active = brand, idle = secondary
        listening
          ? "bg-destructive text-destructive-foreground animate-pulse"
          : "bg-primary text-primary-foreground hover:bg-primary/90",
        // Hidden when accessibility mode is off (still focusable via keyboard)
        !accessibilityMode && "opacity-80 hover:opacity-100",
      )}
    >
      {listening ? (
        <MicOff className="h-6 w-6" aria-hidden="true" />
      ) : (
        <Mic className="h-6 w-6" aria-hidden="true" />
      )}
      <span className="sr-only">{label}</span>
    </button>
  );
}

