/**
 * AccessibilityToggle.tsx
 * A toggle button for the app header that enables/disables accessibility mode.
 * When turned on it announces "Voice control on. Press V to speak." via the
 * aria-live region in VoiceProvider.
 */

import { Accessibility } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useVoice } from "@/voice/VoiceProvider";

export function AccessibilityToggle() {
  const { accessibilityMode, setAccessibilityMode } = useVoice();

  return (
    <Button
      variant={accessibilityMode ? "default" : "outline"}
      size="sm"
      aria-pressed={accessibilityMode}
      aria-label={
        accessibilityMode ? "Accessibility mode on — click to disable" : "Enable accessibility mode"
      }
      onClick={() => setAccessibilityMode(!accessibilityMode)}
      className="focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Accessibility className="h-4 w-4" aria-hidden="true" />
      <span className="hidden sm:inline ml-1.5">
        {accessibilityMode ? "A11y: on" : "A11y"}
      </span>
    </Button>
  );
}

