import { Clock } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { cn } from "@/lib/utils";

function secondsLeft(targetMs: number, skewMs: number): number {
  return Math.max(0, Math.ceil((targetMs - (Date.now() + skewMs)) / 1000));
}

function format(total: number): string {
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  const mm = String(m).padStart(2, "0");
  const ss = String(s).padStart(2, "0");
  return h > 0 ? `${h}:${mm}:${ss}` : `${mm}:${ss}`;
}

interface QuizTimerProps {
  /** Server deadline (ISO). */
  expiresAt: string;
  /** serverClock - deviceClock, so a wrong device clock does not matter. */
  skewMs: number;
  onExpire: () => void;
}

export function QuizTimer({ expiresAt, skewMs, onExpire }: QuizTimerProps) {
  const target = new Date(expiresAt).getTime();
  const [seconds, setSeconds] = useState(() => secondsLeft(target, skewMs));
  const expireRef = useRef(onExpire);
  expireRef.current = onExpire;
  const firedRef = useRef(false);

  useEffect(() => {
    const tick = () => {
      const left = secondsLeft(target, skewMs);
      setSeconds(left);
      if (left <= 0 && !firedRef.current) {
        firedRef.current = true;
        expireRef.current();
      }
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [target, skewMs]);

  // Changes only at thresholds, so a screen reader announces it a few times, not every second.
  const announcement =
    seconds <= 0
      ? "Time is up. Submitting your answers."
      : seconds <= 30
        ? "30 seconds remaining."
        : seconds <= 60
          ? "1 minute remaining."
          : seconds <= 300
            ? "5 minutes remaining."
            : "";

  return (
    <div>
      <p
        role="timer"
        aria-live="off"
        aria-label="Time remaining"
        className={cn(
          "flex items-center gap-2 font-mono text-lg font-semibold transition-colors",
          seconds <= 60 && "text-destructive",
          seconds <= 30 && "animate-soft-pulse",
        )}
      >
        <Clock className="h-5 w-5" aria-hidden="true" />
        {format(seconds)}
      </p>
      <p role="status" className="sr-only">
        {announcement}
      </p>
    </div>
  );
}
