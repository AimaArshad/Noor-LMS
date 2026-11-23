/**
 * Local (client-side) voice navigation, tried by VoiceProvider BEFORE the
 * backend: it lets a student reach the audiobooks from any page by voice and
 * start a book by name even when the server cannot resolve it.
 *
 * Returns a synthetic voice command, or null to let the backend handle it.
 */
import type { VoiceCommandResponse } from "@/voice/voiceClient";

import { playerApi } from "./playerApi";
import { extractBookName, findAudiobook, matchPageNavigation } from "./voiceNavigationLogic";

function navCommand(path: string, speech: string, state?: unknown): VoiceCommandResponse {
  return {
    intent: "navigate",
    action: "navigate",
    target: { path, state },
    speech,
  } as unknown as VoiceCommandResponse;
}

export async function resolveNavigation(transcript: string): Promise<VoiceCommandResponse | null> {
  // 1. "play <book name>" / "open audiobook <name>"
  const name = extractBookName(transcript);
  if (name) {
    try {
      const books = await playerApi.listAll();
      const book = findAudiobook(name, books);
      if (book) {
        const speech = `Playing ${book.title.replace(/[-_]/g, " ")}.`;
        const play = {
          intent: "play",
          action: "play",
          target: { audiobook_id: book.id },
          speech,
        } as unknown as VoiceCommandResponse;
        const { router } = await import("@/routes/index");
        // Already in that book: the player handles a plain "play" itself.
        if (router.state.location.pathname === `/audiobooks/${book.id}`) return play;
        return navCommand(`/audiobooks/${book.id}`, speech, { pendingCommand: play });
      }
    } catch {
      /* fall through to the backend */
    }
  }

  // 2. Pages: home, classes, to-do, audiobook library
  const page = matchPageNavigation(transcript);
  if (page) {
    return navCommand(page.path, page.speech, page.kind === "library" ? { announceList: true } : undefined);
  }
  return null;
}
