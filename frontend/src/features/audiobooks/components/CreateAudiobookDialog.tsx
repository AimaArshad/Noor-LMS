import { BookAudio, Upload } from "lucide-react";
import { useRef, useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { filesApi } from "@/features/files/api";
import { useCreateAudiobook } from "@/features/audiobooks/hooks";

const ACCEPTED_TYPES = [
  "application/pdf",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "text/plain",
];
const ACCEPTED_EXTENSIONS = ".pdf,.docx,.txt";
const MAX_SIZE_BYTES = 25 * 1024 * 1024; // 25 MB
const MAX_SIZE_LABEL = "25 MB";

function humanSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Props {
  classroomId: string;
}

export function CreateAudiobookDialog({ classroomId }: Props) {
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [uploadPct, setUploadPct] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const fileInputRef = useRef<HTMLInputElement>(null);
  const createMutation = useCreateAudiobook(classroomId);

  const reset = () => {
    setFile(null);
    setTitle("");
    setUploadPct(null);
    setError(null);
    setBusy(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setError(null);
    const f = e.target.files?.[0] ?? null;
    if (!f) {
      setFile(null);
      return;
    }

    // Client-side type check
    if (!ACCEPTED_TYPES.includes(f.type) && !f.name.match(/\.(pdf|docx|txt)$/i)) {
      setError("Only PDF, DOCX, and TXT files are supported.");
      setFile(null);
      return;
    }

    // Client-side size check
    if (f.size > MAX_SIZE_BYTES) {
      setError(`File is too large (${humanSize(f.size)}). Maximum is ${MAX_SIZE_LABEL}.`);
      setFile(null);
      return;
    }

    setFile(f);
    // Pre-fill the title from the filename if the user hasn't typed one
    if (!title.trim()) {
      const baseName = f.name.replace(/\.[^.]+$/, "");
      setTitle(baseName);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!file) {
      setError("Please choose a file.");
      return;
    }

    setBusy(true);
    setError(null);
    setUploadPct(0);

    try {
      // 1. Upload file
      const uploaded = await filesApi.upload(file, (pct) => setUploadPct(pct));
      setUploadPct(100);

      // 2. Create audiobook
      await createMutation.mutateAsync({
        file_id: uploaded.id,
        title: title.trim() || undefined,
      });

      setOpen(false);
      reset();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        setOpen(next);
        if (!next) reset();
      }}
    >
      <DialogTrigger asChild>
        <Button type="button" size="sm">
          <BookAudio className="h-4 w-4" aria-hidden="true" />
          <span className="ml-1.5">Create audiobook</span>
        </Button>
      </DialogTrigger>

      <DialogContent className="max-w-lg">
        <form onSubmit={(e) => void handleSubmit(e)}>
          <DialogHeader>
            <DialogTitle>Create audiobook</DialogTitle>
            <DialogDescription>
              Upload a PDF, DOCX, or TXT file (max {MAX_SIZE_LABEL}). The system will extract its
              structure and generate audio.
            </DialogDescription>
          </DialogHeader>

          <div className="mt-4 space-y-4">
            {/* File input */}
            <div className="space-y-1.5">
              <Label htmlFor="audiobook-file">Document file</Label>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  disabled={busy}
                >
                  <Upload className="mr-1.5 h-4 w-4" aria-hidden="true" />
                  Choose file
                </Button>
                <span className="truncate text-sm text-muted-foreground">
                  {file ? `${file.name} (${humanSize(file.size)})` : "No file selected"}
                </span>
              </div>
              <input
                ref={fileInputRef}
                id="audiobook-file"
                type="file"
                accept={ACCEPTED_EXTENSIONS}
                onChange={handleFileChange}
                className="sr-only"
                aria-label="Choose a PDF, DOCX or TXT file"
                disabled={busy}
              />
            </div>

            {/* Title input */}
            <div className="space-y-1.5">
              <Label htmlFor="audiobook-title">Title (optional)</Label>
              <Input
                id="audiobook-title"
                type="text"
                placeholder="Defaults to the file name"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={512}
                disabled={busy}
              />
            </div>

            {/* Upload progress */}
            {uploadPct != null ? (
              <div className="space-y-1">
                <div
                  className="h-2 w-full overflow-hidden rounded-full bg-muted"
                  role="progressbar"
                  aria-valuenow={uploadPct}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-label={`Upload progress: ${uploadPct}%`}
                >
                  <div
                    className="h-full rounded-full bg-primary transition-[width] duration-200"
                    style={{ width: `${uploadPct}%` }}
                  />
                </div>
                <p className="text-xs text-muted-foreground" aria-live="polite">
                  {uploadPct < 100 ? `Uploading… ${uploadPct}%` : "Processing…"}
                </p>
              </div>
            ) : null}

            <ErrorAlert message={error} />
          </div>

          <DialogFooter className="mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => {
                setOpen(false);
                reset();
              }}
              disabled={busy}
            >
              Cancel
            </Button>
            <Button type="submit" disabled={busy || !file}>
              {busy ? "Creating…" : "Create"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

