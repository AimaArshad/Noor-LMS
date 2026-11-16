import { Download, ExternalLink, FileText, Music } from "lucide-react";
import { useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { filesApi } from "@/features/files/api";
import { useFileBlobUrl } from "@/features/files/hooks";
import { saveBlob } from "@/lib/files";
import type { AttachmentRef } from "@/types";

const OPENABLE = new Set(["application/pdf", "text/plain"]);

function AttachmentItem({ attachment }: { attachment: AttachmentRef }) {
  const mime = attachment.mime_type ?? "";
  const isImage = mime.startsWith("image/");
  const isAudio = mime.startsWith("audio/");
  const [audioRequested, setAudioRequested] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const image = useFileBlobUrl(attachment.file_id, isImage);
  const audio = useFileBlobUrl(attachment.file_id, isAudio && audioRequested);

  async function download() {
    setError(null);
    try {
      saveBlob(await filesApi.blob(attachment.file_id), attachment.name);
    } catch (err) {
      setError(getErrorMessage(err, "Could not download the file."));
    }
  }

  async function openInTab() {
    setError(null);
    const tab = window.open("", "_blank"); // opened synchronously so popup blockers allow it
    try {
      const blob = await filesApi.blob(attachment.file_id);
      const url = URL.createObjectURL(blob);
      if (tab) {
        tab.opener = null;
        tab.location.href = url;
      } else {
        saveBlob(blob, attachment.name);
      }
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (err) {
      tab?.close();
      setError(getErrorMessage(err, "Could not open the file."));
    }
  }

  return (
    <li className="space-y-2 rounded-md border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-2 text-sm font-medium">
          {isAudio ? (
            <Music className="h-4 w-4 shrink-0" aria-hidden="true" />
          ) : (
            <FileText className="h-4 w-4 shrink-0" aria-hidden="true" />
          )}
          <span className="break-all">{attachment.name}</span>
        </span>
        <span className="flex gap-2">
          {OPENABLE.has(mime) ? (
            <Button type="button" variant="outline" size="sm" onClick={() => void openInTab()}>
              <ExternalLink aria-hidden="true" />
              Open
              <span className="sr-only"> {attachment.name} in a new tab</span>
            </Button>
          ) : null}
          {isAudio && !audioRequested ? (
            <Button type="button" variant="outline" size="sm" onClick={() => setAudioRequested(true)}>
              Load player
              <span className="sr-only"> for {attachment.name}</span>
            </Button>
          ) : null}
          <Button type="button" variant="outline" size="sm" onClick={() => void download()}>
            <Download aria-hidden="true" />
            Download
            <span className="sr-only"> {attachment.name}</span>
          </Button>
        </span>
      </div>

      {isImage ? (
        image.url ? (
          <img
            src={image.url}
            alt={`Preview of ${attachment.name}`}
            className="max-h-64 rounded-md border object-contain"
          />
        ) : image.error ? (
          <p className="text-xs text-destructive">{image.error}</p>
        ) : (
          <p className="text-xs text-muted-foreground">Loading preview…</p>
        )
      ) : null}
      {isAudio && audioRequested ? (
        audio.url ? (
          // eslint-disable-next-line jsx-a11y/media-has-caption
          <audio controls src={audio.url} className="w-full" aria-label={`Audio: ${attachment.name}`} />
        ) : audio.error ? (
          <p className="text-xs text-destructive">{audio.error}</p>
        ) : (
          <p className="text-xs text-muted-foreground">Loading audio…</p>
        )
      ) : null}
      {error ? (
        <p role="alert" className="text-xs text-destructive">
          {error}
        </p>
      ) : null}
    </li>
  );
}

export function AttachmentList({
  attachments,
  label = "Attachments",
}: {
  attachments: AttachmentRef[];
  label?: string;
}) {
  if (attachments.length === 0) return null;
  return (
    <section aria-label={label} className="space-y-2">
      <h3 className="text-sm font-semibold">{label}</h3>
      <ul className="space-y-2">
        {attachments.map((attachment) => (
          <AttachmentItem key={attachment.file_id} attachment={attachment} />
        ))}
      </ul>
    </section>
  );
}
