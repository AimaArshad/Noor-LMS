import { useEffect } from "react";
import { useNavigate } from "react-router-dom";

import { useVoice } from "@/voice/VoiceProvider";
import { wantsAudiobook } from "@/features/audiobooks/playerLogic";

/**
 * On pages that are not the player: when a voice command asks to play an
 * audiobook ("play physics 2nd year", "go to chapter 2 ..."), open its player
 * and hand the command over so it is carried out once the book has loaded.
 */
export function useAudiobookVoiceNavigation() {
  const { onCommand } = useVoice();
  const navigate = useNavigate();

  useEffect(
    () =>
      onCommand((cmd) => {
        const id = wantsAudiobook(cmd);
        if (id) navigate(`/audiobooks/${id}`, { state: { pendingCommand: cmd } });
      }),
    [onCommand, navigate],
  );
}
