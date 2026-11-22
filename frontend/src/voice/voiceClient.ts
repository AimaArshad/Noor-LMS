/**
 * voiceClient.ts
 * HTTP helpers for the voice command and transcription endpoints.
 * Uses the shared `api` Axios instance (auth + refresh interceptors included).
 */

import { api } from "@/api/client";

// ---------------------------------------------------------------------------
// Types — mirroring backend/app/schemas/voice.py exactly
// ---------------------------------------------------------------------------

export interface VoiceTarget {
  audiobook_id: string | null;
  section_seq: number | null;
  segment_seq: number | null;
  page: number | null;
}

export interface VoiceCommandResponse {
  intent: string;
  action: string;
  target: VoiceTarget;
  speech: string;
}

export interface TranscribeResponse {
  text: string;
  language: string;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/voice/command
 *
 * @param text        Voice transcript text (1–2000 chars).
 * @param audiobookId Optional UUID string to pin the target audiobook.
 */
export async function sendCommand(
  text: string,
  audiobookId?: string,
): Promise<VoiceCommandResponse> {
  const { data } = await api.post<VoiceCommandResponse>("/voice/command", {
    text,
    audiobook_id: audiobookId ?? null,
  });
  return data;
}

/**
 * POST /api/v1/voice/transcribe
 *
 * Sends the audio Blob as multipart/form-data with the field name "audio".
 *
 * @param blob     Audio blob (WAV, WebM, MP3, OGG — max 10 MB).
 * @param filename Optional filename hint (defaults to "recording.webm").
 */
export async function transcribeBlob(
  blob: Blob,
  filename = "recording.webm",
): Promise<TranscribeResponse> {
  const form = new FormData();
  form.append("audio", blob, filename);
  const { data } = await api.post<TranscribeResponse>("/voice/transcribe", form, {
    headers: { "Content-Type": "multipart/form-data" },
    // TTS + Whisper can be slow on first call; give it extra time.
    timeout: 60_000,
  });
  return data;
}

