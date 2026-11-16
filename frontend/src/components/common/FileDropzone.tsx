import { Loader2, Trash2, UploadCloud } from "lucide-react";
import { useRef, useState, type ChangeEvent, type DragEvent } from "react";

import { getErrorMessage } from "@/api/errors";
import { Button } from "@/components/ui/button";
import { filesApi } from "@/features/files/api";
import { ACCEPT, MAX_UPLOAD_MB, validateFile } from "@/lib/files";
import { cn } from "@/lib/utils";
import type { AttachmentRef } from "@/types";

interface PendingUpload {
  key: string;
  name: string;
  progress: number;
  error: string | null;
}

interface FileDropzoneProps {
  id: string;
  label: string;
  value: AttachmentRef[];
  onChange: (next: AttachmentRef[]) => void;
  disabled?: boolean;
  maxFiles?: number;
  error?: string | null;
}

/**
 * Drag-and-drop (or button) file picker. Each file is uploaded at once with
 * `POST /files/upload`; `value` holds the resulting attachment references.
 */
export function FileDropzone({
  id,
  label,
  value,
  onChange,
  disabled = false,
  maxFiles = 20,
  error,
}: FileDropzoneProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const valueRef = useRef(value);
  valueRef.current = value; // always the latest list, even in the middle of a multi-file upload
  const counter = useRef(0);
  const [pending, setPending] = useState<PendingUpload[]>([]);
  const [dragging, setDragging] = useState(false);

  const busy = pending.some((p) => !p.error);

  async function uploadOne(file: File) {
    const key = `${Date.now()}-${counter.current++}`;
    const fail = (message: string) =>
      setPending((list) => [...list, { key, name: file.name, progress: 0, error: message }]);

    const problem = validateFile(file);
    if (problem) return fail(problem);
    if (valueRef.current.length >= maxFiles) return fail(`You can attach at most ${maxFiles} files.`);

    setPending((list) => [...list, { key, name: file.name, progress: 0, error: null }]);
    try {
      const uploaded = await filesApi.upload(file, (percent) =>
        setPending((list) => list.map((p) => (p.key === key ? { ...p, progress: percent } : p))),
      );
      valueRef.current = [
        ...valueRef.current,
        { file_id: uploaded.id, name: uploaded.original_name, mime_type: uploaded.mime_type },
      ];
      onChange(valueRef.current);
      setPending((list) => list.filter((p) => p.key !== key));
    } catch (err) {
      setPending((list) => list.map((p) => (p.key === key ? { ...p, error: getErrorMessage(err) } : p)));
    }
  }

  async function handleFiles(files: FileList | null) {
    if (!files) return;
    for (const file of Array.from(files)) await uploadOne(file); // sequential: predictable order and limits
  }

  function onInputChange(event: ChangeEvent<HTMLInputElement>) {
    const files = event.target.files;
    void handleFiles(files).finally(() => {
      event.target.value = ""; // allow choosing the same file again
    });
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setDragging(false);
    if (!disabled) void handleFiles(event.dataTransfer.files);
  }

  function removeFile(fileId: string) {
    valueRef.current = valueRef.current.filter((a) => a.file_id !== fileId);
    onChange(valueRef.current);
    // Best effort: frees the stored bytes. A file that is already attached elsewhere answers 409; ignore it.
    void filesApi.remove(fileId).catch(() => undefined);
  }

  return (
    <div className="space-y-2">
      <p id={`${id}-label`} className="text-sm font-medium">
        {label}
      </p>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cn(
          "flex flex-col items-center gap-2 rounded-lg border-2 border-dashed p-6 text-center text-sm transition-colors",
          dragging && "border-primary bg-primary/5",
          disabled && "opacity-50",
        )}
      >
        <UploadCloud className="h-6 w-6 text-muted-foreground" aria-hidden="true" />
        <p>Drag files here, or</p>
        <Button
          type="button"
          variant="outline"
          size="sm"
          disabled={disabled}
          aria-describedby={`${id}-help`}
          onClick={() => inputRef.current?.click()}
        >
          Choose files
        </Button>
        <input
          ref={inputRef}
          id={id}
          type="file"
          multiple
          accept={ACCEPT}
          className="sr-only"
          tabIndex={-1}
          aria-hidden="true"
          disabled={disabled}
          onChange={onInputChange}
        />
        <p id={`${id}-help`} className="text-xs text-muted-foreground">
          pdf, docx, pptx, images, zip, mp3, wav, txt · up to {MAX_UPLOAD_MB} MB each
        </p>
      </div>

      <div aria-live="polite">
        {busy ? <p className="sr-only">Uploading files…</p> : null}
        <ul aria-labelledby={`${id}-label`} className="space-y-1">
          {value.map((attachment) => (
            <li
              key={attachment.file_id}
              className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm"
            >
              <span className="min-w-0 break-all">{attachment.name}</span>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                disabled={disabled}
                onClick={() => removeFile(attachment.file_id)}
              >
                <Trash2 aria-hidden="true" />
                <span className="sr-only">Remove {attachment.name}</span>
              </Button>
            </li>
          ))}
          {pending.map((upload) => (
            <li key={upload.key} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
              <span className="min-w-0 break-all">{upload.name}</span>
              {upload.error ? (
                <span className="flex items-center gap-2">
                  <span role="alert" className="text-destructive">
                    {upload.error}
                  </span>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setPending((list) => list.filter((p) => p.key !== upload.key))}
                  >
                    Dismiss
                  </Button>
                </span>
              ) : (
                <span className="flex items-center gap-2 text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                  {upload.progress}%
                </span>
              )}
            </li>
          ))}
        </ul>
      </div>
      {busy ? <p className="text-xs text-muted-foreground">Wait for uploads to finish before saving.</p> : null}
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
