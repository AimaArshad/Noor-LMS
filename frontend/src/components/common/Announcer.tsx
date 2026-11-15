import { useEffect, useState } from "react";

/**
 * A polite live region for results that have no visible counterpart (a class was created, a
 * class was joined, ...). The text is set one tick after mount so that assistive tech, which
 * only announces *changes* to a live region, still reads a message that is present on arrival.
 */
export function Announcer({ message }: { message?: string | null }) {
  const [text, setText] = useState("");

  useEffect(() => {
    if (!message) return;
    const timer = setTimeout(() => setText(message), 100);
    return () => clearTimeout(timer);
  }, [message]);

  return (
    <p role="status" aria-live="polite" className="sr-only">
      {text}
    </p>
  );
}
