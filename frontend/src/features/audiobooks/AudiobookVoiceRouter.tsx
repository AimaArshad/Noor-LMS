import { useEffect } from "react";

import type { VoiceCommandResponse } from "@/voice/voiceClient";

import { wantsAudiobook } from "./playerLogic";

interface Props {
  /** VoiceProvider's onCommand: registers a handler, returns an unsubscribe. */
  onCommand: (handler: (cmd: VoiceCommandResponse) => void) => () => void;
}

/**
 * Rendered once inside VoiceProvider, so voice navigation works on every page.
 *  - "navigate" commands (home, classes, audiobooks, play <name>) change the route.
 *  - a backend-resolved "play / go to chapter ..." for some book opens its player
 *    (when already inside a player, the player handles its own commands).
 * Uses the router object directly so it does not depend on where the provider
 * sits in the tree.
 */
export function AudiobookVoiceRouter({ onCommand }: Props) {
  useEffect(
    () =>
      onCommand((cmd: VoiceCommandResponse) => {
        void (async () => {
          const { router } = await import("@/routes/index");
          const c = (cmd ?? {}) as unknown as { intent?: unknown; target?: { path?: unknown; state?: unknown } };

          if (c.intent === "navigate" && typeof c.target?.path === "string") {
            void router.navigate(c.target.path, { state: c.target.state });
            return;
          }
          if (router.state.location.pathname.startsWith("/audiobooks/")) return;
          const id = wantsAudiobook(cmd);
          if (id) void router.navigate(`/audiobooks/${id}`, { state: { pendingCommand: cmd } });
        })();
      }),
    [onCommand],
  );
  return null;
}
