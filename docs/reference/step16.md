```ts
STEP 16: Assignment and quiz flows (student and teacher)
What is new. Routes are /classes/:classroomId/assignments/:id, /quizzes/new and /quizzes/:id. These match the links the backend already puts in notifications and to-do items. The /classrooms/... redirect from STEP 15 sends them here.
Design decisions:
react-hook-form + zod. 
oAll form fields are strings, so zod input and output types are identical. There is no coerce or transform, which avoids resolver typing problems.
oNumbers are converted in a small toPayload step at submit.
oZod is pinned to v3 to match @hookform/resolvers v3.
Files. 
oThe dropzone uploads on selection (POST /files/upload, with progress and client-side type and size checks). The form then holds AttachmentRefs, and the final request carries them.
oThe server still verifies ownership and content.
oAttachment previews use authenticated blob fetches, because <img src> cannot send a bearer token: inline thumbnails for images, "Open" for pdf and txt, an on-demand player for audio, and a download button for the rest.
oRemoving a freshly uploaded file deletes it on the server (best effort). Files uploaded and then abandoned by closing a dialog stay orphaned until a cleanup job exists.
Assignment states for students. 
oAssigned or Missing (overdue), then Turned in, then Graded (grade shown) or Returned.
oGrades stay hidden until the teacher returns the work. This is a backend rule.
oA resubmission after "returned" clears the grade, and the form says so.
Teacher submissions table. 
oEach row has its own grade and feedback form (validated against max_points).
oSave grade and Return are separate actions. Return is disabled while the row has unsaved edits, so you can't return a grade you haven't saved.
o"View work" shows the student's text and attachments.
Quiz timer is server-based. 
oThe remaining time comes from the server's expires_at.
oThe client reads the server clock from the HTTP Date header to compensate for a wrong device clock. That header is not readable cross-origin by default, so there is a one-line backend edit below.
oThe timer auto-submits at zero. The backend allows 10 seconds of grace.
Quiz taking. 
oAnswers are kept in sessionStorage, so a page refresh resumes the same attempt through /start.
oThe question navigator marks answered questions.
oA beforeunload guard warns about leaving.
oUnanswered questions need a confirmation.
oTime warnings are announced politely to screen readers at 5 min, 1 min and 30 s. This is groundwork for Phase 2.
Results screen. It shows per-question correct or incorrect and points, but never the answer key, because the backend doesn't send it.
Quiz builder. 
ouseFieldArray is nested for questions and options.
oMCQ: 2-10 options and one correct.
oTrue/False: fixed True/False options and one correct.
oShort answer: optional accepted answers. With none, it is graded manually. The teacher grades it in the review row of the results table (the manual-grading endpoint from STEP 10).
oRules mirror the backend: unique option texts, at most 200 questions, total points ≤ 99 999.99, and a published quiz needs at least one question.
oQuestions can be reordered with move up and move down buttons.
The quiz dialog from STEP 15 is replaced by the full builder page. Delete CreateQuizDialog.tsx.
Files in this step
backend/app/main.py                                   ← EDIT (1 line)
frontend/
├── package.json                                      ← EDIT (+3 deps)
└── src/
    ├── types/index.ts                                ← EDIT (append; replace 2 interfaces)
    ├── routes/index.tsx                              ← REPLACE
    ├── lib/{files,forms}.ts                          ← NEW
    ├── components/common/{FileDropzone,AttachmentList}.tsx   ← NEW
    ├── components/layout/…                           (none)
    ├── features/
    │   ├── classrooms/components/ClassroomTabs.tsx   ← REPLACE (Classwork stays active on detail pages)
    │   ├── files/{api,hooks}.ts                      ← NEW
    │   ├── assignments/{api,hooks,schemas}.ts        ← REPLACE, REPLACE, NEW
    │   ├── assignments/components/
    │   │   ├── CreateAssignmentDialog.tsx            ← REPLACE (react-hook-form + zod + attachments)
    │   │   ├── AssignmentsSection.tsx                ← EDIT (title links)
    │   │   ├── SubmissionStatus.tsx                  ← NEW
    │   │   ├── SubmissionForm.tsx                    ← NEW
    │   │   └── SubmissionsTable.tsx                  ← NEW
    │   └── quizzes/
    │       ├── {api,hooks}.ts                        ← REPLACE
    │       ├── schemas.ts                            ← NEW
    │       └── components/
    │           ├── QuizzesSection.tsx                ← REPLACE
    │           ├── CreateQuizDialog.tsx              ← DELETE
    │           ├── QuizBuilder.tsx, QuestionEditor.tsx          ← NEW
    │           ├── QuizTimer.tsx, QuizTaker.tsx, QuizResultView.tsx, StudentQuizView.tsx ← NEW
    │           └── TeacherQuizView.tsx, QuizResultsTable.tsx    ← NEW
    └── pages/classroom/{AssignmentPage,QuizPage,QuizBuilderPage}.tsx ← NEW
cd frontend
npm install react-hook-form@^7.54.2 zod@^3.24.1 @hookform/resolvers@^3.10.0

cd src
rm features/quizzes/components/CreateQuizDialog.tsx
mkdir -p features/files
touch lib/{files,forms}.ts \
  components/common/{FileDropzone,AttachmentList}.tsx \
  features/files/{api,hooks}.ts \
  features/assignments/schemas.ts \
  features/assignments/components/{SubmissionStatus,SubmissionForm,SubmissionsTable}.tsx \
  features/quizzes/schemas.ts \
  features/quizzes/components/{QuizBuilder,QuestionEditor,QuizTimer,QuizTaker,QuizResultView,StudentQuizView,TeacherQuizView,QuizResultsTable}.tsx \
  pages/classroom/{AssignmentPage,QuizPage,QuizBuilderPage}.tsx
Edits
Backend app/main.py, so the browser can read the server clock:
        expose_headers=["Content-Range", "Content-Disposition", "Accept-Ranges", "Date"],
    "@hookform/resolvers": "^3.10.0",
    "react-hook-form": "^7.54.2",
    "zod": "^3.24.1",
// 1) DELETE the existing `AttemptResult` and `QuizResults` interfaces from STEP 15,
// 2) then APPEND everything below.

export type QuestionType = "mcq" | "true_false" | "short_answer";

export interface QuizOptionPublic {
  id: string;
  text: string;
}
export interface QuizOptionKey extends QuizOptionPublic {
  is_correct: boolean;
}
interface QuizQuestionBase {
  id: string;
  prompt: string;
  type: QuestionType;
  points: number;
  order_index: number;
}
export interface StudentQuestion extends QuizQuestionBase {
  options: QuizOptionPublic[];
}
export interface TeacherQuestion extends QuizQuestionBase {
  quiz_id: string;
  options: QuizOptionKey[];
}
/** `GET /quizzes/{id}` for students: no answer key. */
export interface StudentQuiz extends QuizSummary {
  view: "student";
  questions: StudentQuestion[];
}
/** `GET /quizzes/{id}` for teachers: with the answer key. */
export interface TeacherQuiz extends QuizSummary {
  view: "teacher";
  questions: TeacherQuestion[];
}
export type QuizView = StudentQuiz | TeacherQuiz;

export interface AnswerResult {
  question_id: string;
  selected_option_id: string | null;
  answer_text: string | null;
  /** null = awaiting manual grading */
  is_correct: boolean | null;
  points_awarded: number | null;
}

export interface AttemptResult {
  id: string;
  quiz_id: string;
  student_id: string;
  student: UserPublic | null;
  started_at: string;
  submitted_at: string | null;
  expires_at: string | null;
  score: number | null;
  max_score: number | null;
  pending_manual_grading: boolean;
  answers: AnswerResult[];
}

export interface AttemptStart {
  attempt_id: string;
  quiz_id: string;
  started_at: string;
  expires_at: string | null;
  quiz: StudentQuiz;
}

export interface QuizResults {
  quiz_id: string;
  attempt_count: number;
  submitted_count: number;
  not_attempted_count: number;
  average_score: number | null;
  max_score: number;
  limit: number;
  offset: number;
  attempts: AttemptResult[];
}

export interface QuizOptionInput {
  text: string;
  is_correct: boolean;
}
export interface QuizQuestionInput {
  prompt: string;
  type: QuestionType;
  points: number;
  options: QuizOptionInput[];
}
export interface QuizCreatePayload {
  title: string;
  description?: string;
  time_limit_minutes?: number;
  due_at?: string;
  allow_retake: boolean;
  published: boolean;
  questions: QuizQuestionInput[];
}

export interface UploadedFile {
  id: string;
  uploader_id: string | null;
  original_name: string;
  mime_type: string;
  size_bytes: number;
  created_at: string;
  download_url: string;
}
Helpers
/** Mirrors the backend allow-list (STEP 7). The server re-checks the real content. */
export const ALLOWED_EXTENSIONS = [
  ".pdf", ".docx", ".pptx", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".zip", ".mp3", ".wav", ".txt",
] as const;
export const ACCEPT = ALLOWED_EXTENSIONS.join(",");
export const MAX_UPLOAD_MB = 25;

export function extensionOf(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot < 0 ? "" : name.slice(dot).toLowerCase();
}

/** Returns an error message, or `null` when the file may be uploaded. */
export function validateFile(file: File): string | null {
  const ext = extensionOf(file.name);
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(ext)) {
    return `“${file.name}”: ${ext || "this"} files are not allowed.`;
  }
  if (file.size === 0) return `“${file.name}” is empty.`;
  if (file.size > MAX_UPLOAD_MB * 1024 * 1024) return `“${file.name}” is larger than ${MAX_UPLOAD_MB} MB.`;
  return null;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

/** Save a blob through a temporary link (works with authenticated downloads). */
export function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 10_000);
}
/**
 * Message of a field-array level error. Depending on the resolver version it sits on
 * `.root.message` or `.message`.
 */
export function arrayError(error: unknown): string | undefined {
  const e = error as { message?: unknown; root?: { message?: unknown } } | undefined;
  const message = e?.root?.message ?? e?.message;
  return typeof message === "string" ? message : undefined;
}
Files feature
import { api } from "@/api/client";
import type { UploadedFile } from "@/types";

export const filesApi = {
  /** Multipart upload; `onProgress` receives 0-100. The server verifies type and content. */
  upload: (file: File, onProgress?: (percent: number) => void) => {
    const form = new FormData();
    form.append("file", file);
    return api
      .post<UploadedFile>("/files/upload", form, {
        timeout: 120_000,
        onUploadProgress: (event) => {
          if (event.total) onProgress?.(Math.round((event.loaded * 100) / event.total));
        },
      })
      .then((r) => r.data);
  },

  /** Uploader only, and only while the file is not attached to anything (else 409). */
  remove: (id: string) => api.delete(`/files/${id}`).then(() => undefined),

  /** Authenticated download as a Blob (an <img src> cannot send the bearer token). */
  blob: (id: string) => api.get<Blob>(`/files/${id}`, { responseType: "blob" }).then((r) => r.data),
};
import { useEffect, useState } from "react";

import { getErrorMessage } from "@/api/errors";
import { filesApi } from "@/features/files/api";

interface BlobUrlState {
  url: string | null;
  loading: boolean;
  error: string | null;
}

/** Fetches a file with the bearer token and exposes an object URL (revoked on cleanup). */
export function useFileBlobUrl(fileId: string, enabled: boolean): BlobUrlState {
  const [state, setState] = useState<BlobUrlState>({ url: null, loading: enabled, error: null });

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    let objectUrl: string | null = null;
    setState({ url: null, loading: true, error: null });
    filesApi
      .blob(fileId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setState({ url: objectUrl, loading: false, error: null });
      })
      .catch((err: unknown) => {
        if (!cancelled) setState({ url: null, loading: false, error: getErrorMessage(err, "Could not load the file.") });
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [fileId, enabled]);

  return state;
}
Common components
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
export function FileDropzone({ id, label, value, onChange, disabled = false, maxFiles = 20, error }: FileDropzoneProps) {
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
            <li key={attachment.file_id} className="flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm">
              <span className="min-w-0 break-all">{attachment.name}</span>
              <Button type="button" variant="ghost" size="sm" disabled={disabled} onClick={() => removeFile(attachment.file_id)}>
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
                  <span role="alert" className="text-destructive">{upload.error}</span>
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
      {error ? <p role="alert" className="text-sm text-destructive">{error}</p> : null}
    </div>
  );
}
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
          {isAudio ? <Music className="h-4 w-4 shrink-0" aria-hidden="true" /> : <FileText className="h-4 w-4 shrink-0" aria-hidden="true" />}
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
          <img src={image.url} alt={`Preview of ${attachment.name}`} className="max-h-64 rounded-md border object-contain" />
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
      {error ? <p role="alert" className="text-xs text-destructive">{error}</p> : null}
    </li>
  );
}

export function AttachmentList({ attachments, label = "Attachments" }: { attachments: AttachmentRef[]; label?: string }) {
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
Assignments
import { z } from "zod";

export const attachmentSchema = z.object({
  file_id: z.string().uuid(),
  name: z.string(),
  mime_type: z.string().nullable(),
});

const validDate = (value: string) => !value || !Number.isNaN(new Date(value).getTime());

export const assignmentFormSchema = z.object({
  title: z.string().trim().min(1, "Title is required.").max(255, "At most 255 characters."),
  description: z.string().trim().max(10_000, "At most 10000 characters."),
  due: z.string().refine(validDate, "Enter a valid date and time."),
  points: z
    .string()
    .trim()
    .regex(/^\d+$/, "Enter a whole number.")
    .refine((v) => Number(v) >= 1 && Number(v) <= 100_000, "Enter a number from 1 to 100000."),
  publish: z.boolean(),
  attachments: z.array(attachmentSchema).max(20),
});
export type AssignmentFormValues = z.infer<typeof assignmentFormSchema>;

export const submissionFormSchema = z
  .object({
    content: z.string().max(20_000, "At most 20000 characters."),
    attachments: z.array(attachmentSchema).max(20),
  })
  .refine((v) => v.content.trim().length > 0 || v.attachments.length > 0, {
    message: "Write an answer or attach at least one file.",
    path: ["content"],
  });
export type SubmissionFormValues = z.infer<typeof submissionFormSchema>;

/** Grade must be a number with at most 2 decimals, between 0 and the assignment's points. */
export function gradeFormSchema(maxPoints: number) {
  return z.object({
    grade: z
      .string()
      .trim()
      .regex(/^\d+(\.\d{1,2})?$/, "Enter a number (up to 2 decimals).")
      .refine((v) => Number(v) <= maxPoints, `At most ${maxPoints}.`),
    feedback: z.string().max(5_000, "At most 5000 characters."),
  });
}
export type GradeFormValues = { grade: string; feedback: string };
import { api } from "@/api/client";
import type {
  Assignment,
  AssignmentCreateInput,
  AssignmentState,
  AttachmentRef,
  Page,
  Submission,
  SubmissionList,
} from "@/types";

export interface AssignmentPayload extends AssignmentCreateInput {
  attachments?: AttachmentRef[];
}

export interface SubmitInput {
  content?: string;
  attachments: AttachmentRef[];
}

export const assignmentsApi = {
  /** Students only receive published assignments. */
  list: (classroomId: string) =>
    api
      .get<Page<Assignment>>(`/classrooms/${classroomId}/assignments`, { params: { limit: 100 } })
      .then((r) => r.data),

  get: (id: string) => api.get<Assignment>(`/assignments/${id}`).then((r) => r.data),

  create: (classroomId: string, body: AssignmentPayload) =>
    api.post<Assignment>(`/classrooms/${classroomId}/assignments`, body).then((r) => r.data),

  update: (id: string, body: { state?: AssignmentState }) =>
    api.patch<Assignment>(`/assignments/${id}`, body).then((r) => r.data),

  /** Students: create or update your submission (state becomes turned_in). */
  submit: (id: string, body: SubmitInput) =>
    api.post<Submission>(`/assignments/${id}/submit`, body).then((r) => r.data),

  /** Students: your own submission, or `null` when you have not turned anything in. */
  mySubmission: (id: string) =>
    api.get<Submission | null>(`/assignments/${id}/my-submission`).then((r) => r.data),

  /** Teachers: first 100 submissions plus `not_submitted_count` (used by the Grades tab). */
  submissions: (id: string) =>
    api.get<SubmissionList>(`/assignments/${id}/submissions`, { params: { limit: 100 } }).then((r) => r.data),

  submissionsPage: (id: string, params: { limit: number; offset: number }) =>
    api.get<SubmissionList>(`/assignments/${id}/submissions`, { params }).then((r) => r.data),

  grade: (submissionId: string, body: { grade: number; feedback: string }) =>
    api.patch<Submission>(`/submissions/${submissionId}/grade`, body).then((r) => r.data),

  /** Makes grade and feedback visible to the student and notifies them. */
  returnWork: (submissionId: string) =>
    api.patch<Submission>(`/submissions/${submissionId}/return`).then((r) => r.data),
};
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assignmentsApi, type AssignmentPayload, type SubmitInput } from "@/features/assignments/api";
import type { AssignmentState } from "@/types";

export const SUBMISSIONS_PAGE_SIZE = 25;

export const assignmentKeys = {
  all: ["assignments"] as const,
  list: (classroomId: string) => ["assignments", "list", classroomId] as const,
  detail: (id: string) => ["assignments", "detail", id] as const,
  mySubmission: (id: string) => ["assignments", "my-submission", id] as const,
  /** Prefix of every submissions query of one assignment (the Grades tab and the table). */
  submissions: (id: string) => ["assignments", "submissions", id] as const,
  submissionsPage: (id: string, offset: number) => ["assignments", "submissions", id, "page", offset] as const,
};

export function useAssignments(classroomId: string) {
  return useQuery({
    queryKey: assignmentKeys.list(classroomId),
    queryFn: () => assignmentsApi.list(classroomId),
  });
}

export function useAssignment(id: string) {
  return useQuery({
    queryKey: assignmentKeys.detail(id),
    queryFn: () => assignmentsApi.get(id),
    enabled: Boolean(id),
  });
}

export function useCreateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignmentPayload) => assignmentsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}

export function useUpdateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: AssignmentState }) => assignmentsApi.update(id, { state }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.all }),
    meta: { classroomId },
  });
}

export function useMySubmission(id: string) {
  return useQuery({
    queryKey: assignmentKeys.mySubmission(id),
    queryFn: () => assignmentsApi.mySubmission(id),
  });
}

export function useSubmitAssignment(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: SubmitInput) => assignmentsApi.submit(assignmentId, body),
    onSuccess: (submission) => {
      queryClient.setQueryData(assignmentKeys.mySubmission(assignmentId), submission);
      void queryClient.invalidateQueries({ queryKey: ["todo"] });
    },
  });
}

export function useSubmissionsPage(assignmentId: string, offset: number) {
  return useQuery({
    queryKey: assignmentKeys.submissionsPage(assignmentId, offset),
    queryFn: () => assignmentsApi.submissionsPage(assignmentId, { limit: SUBMISSIONS_PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  });
}

export function useGradeSubmission(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ submissionId, grade, feedback }: { submissionId: string; grade: number; feedback: string }) =>
      assignmentsApi.grade(submissionId, { grade, feedback }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.submissions(assignmentId) }),
  });
}

export function useReturnSubmission(assignmentId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (submissionId: string) => assignmentsApi.returnWork(submissionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.submissions(assignmentId) }),
  });
}
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useCallback } from "react";
import { Controller, useForm } from "react-hook-form";

import { FileDropzone } from "@/components/common/FileDropzone";
import { FormDialog, useFormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import type { AssignmentPayload } from "@/features/assignments/api";
import { useCreateAssignment } from "@/features/assignments/hooks";
import { assignmentFormSchema, type AssignmentFormValues } from "@/features/assignments/schemas";
import { toIsoFromLocalInput } from "@/lib/format";

const DEFAULTS: AssignmentFormValues = {
  title: "",
  description: "",
  due: "",
  points: "100",
  publish: false,
  attachments: [],
};

export function CreateAssignmentDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateAssignment(classroomId);
  const { reset: resetMutation } = create;
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<AssignmentFormValues>({
    resolver: zodResolver(assignmentFormSchema),
    defaultValues: DEFAULTS,
  });

  const resetAll = useCallback(() => {
    reset(DEFAULTS);
    resetMutation();
  }, [reset, resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const submit = handleSubmit((values) => {
    const body: AssignmentPayload = {
      title: values.title,
      max_points: Number(values.points),
      state: values.publish ? "published" : "draft",
      attachments: values.attachments,
    };
    if (values.description) body.description = values.description;
    const dueAt = toIsoFromLocalInput(values.due);
    if (dueAt) body.due_at = dueAt;
    create.mutate(body, { onSuccess: dialog.close });
  });

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Create assignment
        </Button>
      }
      title="Create an assignment"
      description="Save it as a draft, or publish it so students see it and get it on their to-do list."
      submitLabel="Create"
      pendingLabel="Creating…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={() => void submit()}
    >
      <TextField id="assignment-title" label="Title" required autoComplete="off" {...register("title")} error={errors.title?.message} />
      <TextAreaField id="assignment-description" label="Instructions" rows={4} {...register("description")} error={errors.description?.message} />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField id="assignment-due" label="Due date" type="datetime-local" {...register("due")} error={errors.due?.message} />
        <TextField
          id="assignment-points"
          label="Points"
          inputMode="numeric"
          autoComplete="off"
          {...register("points")}
          error={errors.points?.message}
        />
      </div>
      <Controller
        control={control}
        name="attachments"
        render={({ field }) => (
          <FileDropzone
            id="assignment-files"
            label="Attachments"
            value={field.value}
            onChange={field.onChange}
            disabled={create.isPending}
            error={errors.attachments?.message}
          />
        )}
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-primary" {...register("publish")} />
        Publish now
      </label>
    </FormDialog>
  );
}
// 1) add to the imports:
import { Link } from "react-router-dom";

// 2) in AssignmentItem, REPLACE
//      <h3 className="break-words font-medium">{assignment.title}</h3>
//    WITH
            <h3 className="break-words font-medium">
              <Link
                to={`/classes/${classroom.id}/assignments/${assignment.id}`}
                className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {assignment.title}
              </Link>
            </h3>
import { Badge } from "@/components/ui/badge";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { Assignment, Submission } from "@/types";

type Variant = "default" | "secondary" | "destructive" | "outline";

/** What the student sees. Grades appear only after the teacher returns the work. */
function describe(submission: Submission | null | undefined, assignment: Assignment): { label: string; variant: Variant } {
  if (!submission) {
    const overdue = assignment.due_at !== null && new Date(assignment.due_at) < new Date();
    return overdue ? { label: "Missing", variant: "destructive" } : { label: "Assigned", variant: "outline" };
  }
  if (submission.state === "returned") {
    return submission.grade !== null ? { label: "Graded", variant: "default" } : { label: "Returned", variant: "default" };
  }
  return { label: "Turned in", variant: "secondary" };
}

export function SubmissionStatus({
  submission,
  assignment,
}: {
  submission: Submission | null | undefined;
  assignment: Assignment;
}) {
  const { label, variant } = describe(submission, assignment);
  return (
    <section aria-labelledby="your-work-title" className="space-y-3 rounded-lg border p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="your-work-title" className="text-lg font-semibold">Your work</h2>
        <Badge variant={variant}>{label}</Badge>
      </div>

      {submission?.submitted_at ? (
        <p className="text-sm text-muted-foreground">
          Turned in <time dateTime={submission.submitted_at}>{formatDateTime(submission.submitted_at)}</time>
        </p>
      ) : null}

      {submission?.state === "returned" && submission.grade !== null ? (
        <p className="text-2xl font-semibold">
          {formatPoints(submission.grade)} <span className="text-base font-normal text-muted-foreground">/ {assignment.max_points}</span>
        </p>
      ) : null}

      {submission?.state === "returned" && submission.feedback ? (
        <div className="rounded-md bg-muted/50 p-3 text-sm">
          <p className="font-medium">Teacher feedback</p>
          <p className="mt-1 whitespace-pre-wrap break-words">{submission.feedback}</p>
        </div>
      ) : null}
    </section>
  );
}
import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2 } from "lucide-react";
import { Controller, useForm } from "react-hook-form";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { FileDropzone } from "@/components/common/FileDropzone";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { useSubmitAssignment } from "@/features/assignments/hooks";
import { submissionFormSchema, type SubmissionFormValues } from "@/features/assignments/schemas";
import type { Submission } from "@/types";

interface SubmissionFormProps {
  assignmentId: string;
  /** The existing submission, if any (the form starts with its content). */
  submission: Submission | null | undefined;
  disabled: boolean;
}

/** Mount this only after the submission query has resolved: it reads the initial values once. */
export function SubmissionForm({ assignmentId, submission, disabled }: SubmissionFormProps) {
  const submit = useSubmitAssignment(assignmentId);
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<SubmissionFormValues>({
    resolver: zodResolver(submissionFormSchema),
    defaultValues: { content: submission?.content ?? "", attachments: submission?.attachments ?? [] },
  });

  const resubmitting = submission !== null && submission !== undefined;
  const afterReturn = submission?.state === "returned";

  const onValid = handleSubmit((values) => {
    submit.mutate({
      content: values.content.trim() || undefined,
      attachments: values.attachments,
    });
  });

  return (
    <form onSubmit={(e) => void onValid(e)} noValidate className="space-y-4">
      <h2 className="text-lg font-semibold">{resubmitting ? "Update your work" : "Turn in your work"}</h2>
      {afterReturn ? (
        <p role="note" className="rounded-md border bg-secondary p-3 text-sm">
          Resubmitting clears your current grade. Your teacher will grade the new version.
        </p>
      ) : null}
      {disabled ? (
        <p role="note" className="rounded-md border bg-secondary p-3 text-sm">
          This class is archived, so work can no longer be submitted.
        </p>
      ) : null}

      <ErrorAlert message={submit.isError ? getErrorMessage(submit.error) : null} />

      <TextAreaField
        id="submission-content"
        label="Your answer"
        rows={6}
        maxLength={20_000}
        disabled={disabled || submit.isPending}
        {...register("content")}
        error={errors.content?.message}
      />
      <Controller
        control={control}
        name="attachments"
        render={({ field }) => (
          <FileDropzone
            id="submission-files"
            label="Attachments"
            value={field.value}
            onChange={field.onChange}
            disabled={disabled || submit.isPending}
            error={errors.attachments?.message}
          />
        )}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={disabled || submit.isPending}>
          {submit.isPending ? "Submitting…" : resubmitting ? "Resubmit" : "Turn in"}
        </Button>
        <p role="status" className="flex items-center gap-1 text-sm text-muted-foreground">
          {submit.isSuccess ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
              Your work was turned in.
            </>
          ) : null}
        </p>
      </div>
    </form>
  );
}
import { zodResolver } from "@hookform/resolvers/zod";
import { useMemo, useState, type KeyboardEvent } from "react";
import { useForm } from "react-hook-form";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { AttachmentList } from "@/components/common/AttachmentList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  SUBMISSIONS_PAGE_SIZE,
  useGradeSubmission,
  useReturnSubmission,
  useSubmissionsPage,
} from "@/features/assignments/hooks";
import { gradeFormSchema, type GradeFormValues } from "@/features/assignments/schemas";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Submission } from "@/types";

const STATE_LABEL: Record<string, { label: string; variant: "secondary" | "default" | "outline" }> = {
  turned_in: { label: "To grade", variant: "secondary" },
  graded: { label: "Graded", variant: "outline" },
  returned: { label: "Returned", variant: "default" },
};

function SubmissionRow({ submission, assignment, readOnly }: { submission: Submission; assignment: Assignment; readOnly: boolean }) {
  const schema = useMemo(() => gradeFormSchema(assignment.max_points), [assignment.max_points]);
  const grade = useGradeSubmission(assignment.id);
  const ret = useReturnSubmission(assignment.id);
  const {
    register,
    handleSubmit,
    formState: { errors, isDirty },
  } = useForm<GradeFormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      grade: submission.grade === null ? "" : String(submission.grade),
      feedback: submission.feedback ?? "",
    },
  });

  const name = submission.student?.full_name ?? "Unknown student";
  const state = STATE_LABEL[submission.state] ?? STATE_LABEL.turned_in;
  const busy = grade.isPending || ret.isPending;
  const error = grade.isError ? grade.error : ret.isError ? ret.error : null;

  const save = handleSubmit((values) => {
    ret.reset();
    grade.mutate({ submissionId: submission.id, grade: Number(values.grade), feedback: values.feedback.trim() });
  });

  function onKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Enter") {
      event.preventDefault();
      void save();
    }
  }

  return (
    <tr className="align-top">
      <th scope="row" className="min-w-40 px-4 py-3 text-left font-medium">
        {name}
        <details className="mt-2 text-sm font-normal">
          <summary className="cursor-pointer text-primary">View work</summary>
          <div className="mt-2 space-y-3">
            {submission.content ? (
              <p className="whitespace-pre-wrap break-words rounded-md bg-muted/50 p-3">{submission.content}</p>
            ) : (
              <p className="text-muted-foreground">No text answer.</p>
            )}
            <AttachmentList attachments={submission.attachments} label={`Files from ${name}`} />
          </div>
        </details>
      </th>
      <td className="px-4 py-3">
        <Badge variant={state.variant}>{state.label}</Badge>
      </td>
      <td className="whitespace-nowrap px-4 py-3">
        {submission.submitted_at ? <time dateTime={submission.submitted_at}>{formatDateTime(submission.submitted_at)}</time> : "—"}
      </td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-1">
          <Input
            aria-label={`Grade for ${name}`}
            aria-invalid={errors.grade ? true : undefined}
            inputMode="decimal"
            autoComplete="off"
            disabled={readOnly || busy}
            className="w-20"
            onKeyDown={onKeyDown}
            {...register("grade")}
          />
          <span className="text-muted-foreground">/ {assignment.max_points}</span>
        </div>
        {errors.grade ? <p role="alert" className="mt-1 text-xs text-destructive">{errors.grade.message}</p> : null}
      </td>
      <td className="px-4 py-3">
        <Input
          aria-label={`Feedback for ${name}`}
          aria-invalid={errors.feedback ? true : undefined}
          autoComplete="off"
          disabled={readOnly || busy}
          className="min-w-48"
          onKeyDown={onKeyDown}
          {...register("feedback")}
        />
        {errors.feedback ? <p role="alert" className="mt-1 text-xs text-destructive">{errors.feedback.message}</p> : null}
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-wrap gap-2">
          <Button type="button" size="sm" disabled={readOnly || busy || !isDirty} onClick={() => void save()}>
            {grade.isPending ? "Saving…" : "Save grade"}
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            disabled={readOnly || busy || isDirty || submission.state === "returned"}
            onClick={() => {
              grade.reset();
              ret.mutate(submission.id);
            }}
          >
            {ret.isPending ? "Returning…" : "Return"}
            <span className="sr-only"> work to {name}</span>
          </Button>
        </div>
        {isDirty ? <p className="mt-1 text-xs text-muted-foreground">Save before returning.</p> : null}
        <ErrorAlert className="mt-2" message={error ? getErrorMessage(error) : null} />
      </td>
    </tr>
  );
}

export function SubmissionsTable({ assignment, readOnly }: { assignment: Assignment; readOnly: boolean }) {
  const [offset, setOffset] = useState(0);
  const query = useSubmissionsPage(assignment.id, offset);
  const data = query.data;

  return (
    <section aria-labelledby="submissions-title" className="space-y-3">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 id="submissions-title" className="text-xl font-semibold">Submissions</h2>
        {data ? (
          <p className="text-sm text-muted-foreground">
            {data.total} turned in · {data.not_submitted_count} not submitted
          </p>
        ) : null}
      </div>

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={data?.items.length === 0 && offset === 0}
        emptyText="Nobody has turned in work yet."
        loadingLabel="Loading submissions…"
      >
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Student submissions for {assignment.title}</caption>
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Student</th>
                <th scope="col" className="px-4 py-2 font-medium">Status</th>
                <th scope="col" className="px-4 py-2 font-medium">Turned in</th>
                <th scope="col" className="px-4 py-2 font-medium">Grade</th>
                <th scope="col" className="px-4 py-2 font-medium">Feedback</th>
                <th scope="col" className="px-4 py-2 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data?.items.map((s) => (
                // The key includes the server state so a saved row resets its form to the new values.
                <SubmissionRow
                  key={`${s.id}:${s.state}:${s.graded_at ?? ""}:${s.updated_at}`}
                  submission={s}
                  assignment={assignment}
                  readOnly={readOnly}
                />
              ))}
            </tbody>
          </table>
        </div>
        {data && data.total > SUBMISSIONS_PAGE_SIZE ? (
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - SUBMISSIONS_PAGE_SIZE))}>
              Previous
            </Button>
            <p className="text-sm text-muted-foreground">
              {offset + 1}–{Math.min(offset + SUBMISSIONS_PAGE_SIZE, data.total)} of {data.total}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + SUBMISSIONS_PAGE_SIZE >= data.total}
              onClick={() => setOffset(offset + SUBMISSIONS_PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import { getErrorMessage, getStatus } from "@/api/errors";
import { AttachmentList } from "@/components/common/AttachmentList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SubmissionForm } from "@/features/assignments/components/SubmissionForm";
import { SubmissionStatus } from "@/features/assignments/components/SubmissionStatus";
import { SubmissionsTable } from "@/features/assignments/components/SubmissionsTable";
import {
  useAssignment,
  useMySubmission,
  useUpdateAssignment,
} from "@/features/assignments/hooks";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Classroom } from "@/types";

function StudentPanel({ assignment, classroom }: { assignment: Assignment; classroom: Classroom }) {
  const mine = useMySubmission(assignment.id);
  if (mine.isPending) return <Spinner label="Loading your work…" />;
  if (mine.isError) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(mine.error)} />
        <Button variant="outline" size="sm" onClick={() => void mine.refetch()}>Try again</Button>
      </div>
    );
  }
  return (
    <div className="space-y-6">
      <SubmissionStatus submission={mine.data} assignment={assignment} />
      <SubmissionForm
        key={mine.data?.id ?? "new"}
        assignmentId={assignment.id}
        submission={mine.data}
        disabled={classroom.is_archived}
      />
    </div>
  );
}

export function AssignmentPage() {
  const { classroom } = useClassroomContext();
  const { assignmentId = "" } = useParams();
  const { data: assignment, isPending, error, refetch } = useAssignment(assignmentId);
  const publish = useUpdateAssignment(classroom.id);
  useDocumentTitle(assignment ? `${assignment.title} · ${classroom.name}` : classroom.name);

  const back = (
    <Link
      to={`/classes/${classroom.id}/classwork`}
      className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
    >
      <ArrowLeft className="h-4 w-4" aria-hidden="true" />
      Back to classwork
    </Link>
  );

  if (isPending) return <Spinner label="Loading assignment…" />;
  if (error || !assignment || assignment.classroom_id !== classroom.id) {
    const missing = !error || getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="space-y-3 py-6">
        {back}
        <h2 className="text-xl font-semibold">{missing ? "Assignment not found" : "Could not load this assignment"}</h2>
        {!missing ? <Button variant="outline" size="sm" onClick={() => void refetch()}>Try again</Button> : null}
      </div>
    );
  }

  const isTeacher = classroom.my_role === "teacher";
  const canPublish = isTeacher && !classroom.is_archived && assignment.state === "draft";

  return (
    <article className="mx-auto max-w-4xl space-y-6">
      {back}

      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="break-words text-2xl font-semibold tracking-tight">{assignment.title}</h2>
          <div className="flex items-center gap-2">
            {assignment.state === "draft" ? <Badge variant="outline">Draft</Badge> : null}
            {canPublish ? (
              <Button size="sm" disabled={publish.isPending} onClick={() => publish.mutate({ id: assignment.id, state: "published" })}>
                {publish.isPending ? "Publishing…" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {assignment.due_at ? (
            <>Due <time dateTime={assignment.due_at}>{formatDateTime(assignment.due_at)}</time></>
          ) : (
            "No due date"
          )}
          {" · "}
          {assignment.max_points} points
        </p>
        <ErrorAlert message={publish.isError ? getErrorMessage(publish.error) : null} />
      </header>

      {assignment.description ? (
        <p className="whitespace-pre-wrap break-words">{assignment.description}</p>
      ) : (
        <p className="text-muted-foreground">No instructions.</p>
      )}
      <AttachmentList attachments={assignment.attachments} label="Attachments" />

      <hr />

      {isTeacher ? (
        <SubmissionsTable assignment={assignment} readOnly={classroom.is_archived} />
      ) : (
        <StudentPanel assignment={assignment} classroom={classroom} />
      )}
    </article>
  );
}
Quizzes: API, schemas, hooks
import { api } from "@/api/client";
import type {
  AttemptResult,
  AttemptStart,
  MyAttempt,
  Page,
  QuizCreatePayload,
  QuizResults,
  QuizSummary,
  QuizView,
  TeacherQuiz,
} from "@/types";

export interface StartResponse {
  attempt: AttemptStart;
  /** true = new attempt (201), false = an open attempt was resumed (200) */
  created: boolean;
  /** The server clock (from the HTTP Date header), or null when it is not readable. */
  serverNow: number | null;
}

export interface AnswerInput {
  question_id: string;
  selected_option_id?: string;
  answer_text?: string;
}

export const quizzesApi = {
  /** Students only receive published quizzes. */
  list: (classroomId: string) =>
    api.get<Page<QuizSummary>>(`/classrooms/${classroomId}/quizzes`, { params: { limit: 100 } }).then((r) => r.data),

  /** Teachers get the answer key (`view: "teacher"`), students never do. */
  get: (id: string) => api.get<QuizView>(`/quizzes/${id}`).then((r) => r.data),

  create: (classroomId: string, body: QuizCreatePayload) =>
    api.post<TeacherQuiz>(`/classrooms/${classroomId}/quizzes`, body).then((r) => r.data),

  update: (id: string, body: { published: boolean }) =>
    api.patch<TeacherQuiz>(`/quizzes/${id}`, body).then((r) => r.data),

  start: (id: string): Promise<StartResponse> =>
    api.post<AttemptStart>(`/quizzes/${id}/start`).then((r) => {
      const parsed = Date.parse(String(r.headers["date"] ?? ""));
      return { attempt: r.data, created: r.status === 201, serverNow: Number.isNaN(parsed) ? null : parsed };
    }),

  submit: (id: string, answers: AnswerInput[]) =>
    api.post<AttemptResult>(`/quizzes/${id}/submit`, { answers }).then((r) => r.data),

  myAttempt: (id: string) => api.get<MyAttempt>(`/quizzes/${id}/my-attempt`).then((r) => r.data),

  /** Statistics only (one attempt requested): used by the Grades tab. */
  results: (id: string) => api.get<QuizResults>(`/quizzes/${id}/results`, { params: { limit: 1 } }).then((r) => r.data),

  resultsPage: (id: string, params: { limit: number; offset: number }) =>
    api.get<QuizResults>(`/quizzes/${id}/results`, { params }).then((r) => r.data),

  gradeAnswer: (quizId: string, attemptId: string, questionId: string, pointsAwarded: number) =>
    api
      .patch<AttemptResult>(`/quizzes/${quizId}/attempts/${attemptId}/answers/${questionId}`, {
        points_awarded: pointsAwarded,
      })
      .then((r) => r.data),
};
import { z } from "zod";

import type { QuizCreatePayload, QuestionType } from "@/types";
import { toIsoFromLocalInput } from "@/lib/format";

export const MAX_QUESTIONS = 200;
export const MAX_OPTIONS = 10;
const MAX_TOTAL_POINTS = 99_999.99;

const optionSchema = z.object({
  text: z.string().trim().min(1, "Enter the text.").max(1000, "At most 1000 characters."),
});

const questionSchema = z
  .object({
    type: z.enum(["mcq", "true_false", "short_answer"]),
    prompt: z.string().trim().min(1, "Enter the question.").max(5000, "At most 5000 characters."),
    points: z
      .string()
      .trim()
      .regex(/^\d{1,4}(\.\d{1,2})?$/, "Enter a number up to 9999.99 (2 decimals at most).")
      .refine((v) => Number(v) > 0, "Points must be greater than 0."),
    /** Index of the correct option (mcq / true_false). Ignored for short answers. */
    correctIndex: z.number().int().min(0),
    options: z.array(optionSchema).max(MAX_OPTIONS, `At most ${MAX_OPTIONS} options.`),
  })
  .superRefine((q, ctx) => {
    const texts = q.options.map((o) => o.text.trim().toLocaleLowerCase()).filter(Boolean);
    if (new Set(texts).size !== texts.length) {
      ctx.addIssue({ code: "custom", path: ["options"], message: "Each option must be different." });
    }
    if (q.type === "mcq") {
      if (q.options.length < 2) ctx.addIssue({ code: "custom", path: ["options"], message: "Add at least 2 options." });
      if (q.correctIndex >= q.options.length) {
        ctx.addIssue({ code: "custom", path: ["correctIndex"], message: "Mark the correct option." });
      }
    }
    if (q.type === "true_false" && q.correctIndex > 1) {
      ctx.addIssue({ code: "custom", path: ["correctIndex"], message: "Choose True or False." });
    }
  });

export const quizFormSchema = z
  .object({
    title: z.string().trim().min(1, "Title is required.").max(255, "At most 255 characters."),
    description: z.string().trim().max(10_000, "At most 10000 characters."),
    minutes: z
      .string()
      .trim()
      .refine((v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 600), "Enter whole minutes from 1 to 600, or leave empty."),
    due: z.string().refine((v) => !v || !Number.isNaN(new Date(v).getTime()), "Enter a valid date and time."),
    allowRetake: z.boolean(),
    publish: z.boolean(),
    questions: z.array(questionSchema).max(MAX_QUESTIONS, `At most ${MAX_QUESTIONS} questions.`),
  })
  .superRefine((quiz, ctx) => {
    if (quiz.publish && quiz.questions.length === 0) {
      ctx.addIssue({ code: "custom", path: ["questions"], message: "Add at least one question before publishing." });
    }
    const total = quiz.questions.reduce((sum, q) => sum + (Number(q.points) || 0), 0);
    if (total > MAX_TOTAL_POINTS) {
      ctx.addIssue({ code: "custom", path: ["questions"], message: `The total points must not exceed ${MAX_TOTAL_POINTS}.` });
    }
  });

export type QuizFormValues = z.infer<typeof quizFormSchema>;
export type QuestionFormValues = QuizFormValues["questions"][number];

export function newQuestion(type: QuestionType = "mcq"): QuestionFormValues {
  return {
    type,
    prompt: "",
    points: "1",
    correctIndex: 0,
    options: type === "true_false" ? [{ text: "True" }, { text: "False" }] : type === "mcq" ? [{ text: "" }, { text: "" }] : [],
  };
}

/** Form values -> API payload. Runs only on valid values. */
export function toPayload(values: QuizFormValues): QuizCreatePayload {
  const payload: QuizCreatePayload = {
    title: values.title,
    allow_retake: values.allowRetake,
    published: values.publish,
    questions: values.questions.map((q) => ({
      prompt: q.prompt,
      type: q.type,
      points: Number(q.points),
      options:
        q.type === "short_answer"
          ? q.options.map((o) => ({ text: o.text, is_correct: true })) // accepted answers
          : q.type === "true_false"
            ? [
                { text: "True", is_correct: q.correctIndex === 0 },
                { text: "False", is_correct: q.correctIndex === 1 },
              ]
            : q.options.map((o, i) => ({ text: o.text, is_correct: i === q.correctIndex })),
    })),
  };
  if (values.description) payload.description = values.description;
  if (values.minutes) payload.time_limit_minutes = Number(values.minutes);
  const dueAt = toIsoFromLocalInput(values.due);
  if (dueAt) payload.due_at = dueAt;
  return payload;
}
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { quizzesApi, type AnswerInput } from "@/features/quizzes/api";
import type { QuizCreatePayload } from "@/types";

export const RESULTS_PAGE_SIZE = 25;

export const quizKeys = {
  all: ["quizzes"] as const,
  list: (classroomId: string) => ["quizzes", "list", classroomId] as const,
  detail: (id: string) => ["quizzes", "detail", id] as const,
  myAttempt: (id: string) => ["quizzes", "my-attempt", id] as const,
  /** Prefix of every results query of one quiz (Grades tab statistics and the results table). */
  results: (id: string) => ["quizzes", "results", id] as const,
  resultsPage: (id: string, offset: number) => ["quizzes", "results", id, "page", offset] as const,
};

export function useQuizzes(classroomId: string) {
  return useQuery({
    queryKey: quizKeys.list(classroomId),
    queryFn: () => quizzesApi.list(classroomId),
  });
}

export function useQuiz(id: string) {
  return useQuery({
    queryKey: quizKeys.detail(id),
    queryFn: () => quizzesApi.get(id),
    enabled: Boolean(id),
  });
}

export function useCreateQuiz(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: QuizCreatePayload) => quizzesApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.list(classroomId) }),
  });
}

export function useUpdateQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (published: boolean) => quizzesApi.update(quizId, { published }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.all }),
  });
}

export function useMyAttempt(quizId: string) {
  return useQuery({
    queryKey: quizKeys.myAttempt(quizId),
    queryFn: () => quizzesApi.myAttempt(quizId),
  });
}

export function useStartQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => quizzesApi.start(quizId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.myAttempt(quizId) }),
  });
}

export function useSubmitQuiz(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (answers: AnswerInput[]) => quizzesApi.submit(quizId, answers),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: quizKeys.myAttempt(quizId) });
      void queryClient.invalidateQueries({ queryKey: ["todo"] });
    },
  });
}

export function useQuizResultsPage(quizId: string, offset: number) {
  return useQuery({
    queryKey: quizKeys.resultsPage(quizId, offset),
    queryFn: () => quizzesApi.resultsPage(quizId, { limit: RESULTS_PAGE_SIZE, offset }),
    placeholderData: keepPreviousData,
  });
}

export function useGradeAnswer(quizId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (v: { attemptId: string; questionId: string; points: number }) =>
      quizzesApi.gradeAnswer(quizId, v.attemptId, v.questionId, v.points),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.results(quizId) }),
  });
}
Quiz builder (teacher)
import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useFieldArray, useFormContext, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_OPTIONS, type QuizFormValues } from "@/features/quizzes/schemas";
import { arrayError } from "@/lib/forms";
import type { QuestionType } from "@/types";

interface QuestionEditorProps {
  index: number;
  total: number;
  onRemove: () => void;
  onMove: (to: number) => void;
}

const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Multiple choice",
  true_false: "True / False",
  short_answer: "Short answer",
};

const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function QuestionEditor({ index, total, onRemove, onMove }: QuestionEditorProps) {
  const {
    register,
    control,
    setValue,
    formState: { errors },
  } = useFormContext<QuizFormValues>();
  const options = useFieldArray({ control, name: `questions.${index}.options` });
  const type = useWatch({ control, name: `questions.${index}.type` });
  const correct = useWatch({ control, name: `questions.${index}.correctIndex` });
  const qErr = errors.questions?.[index];
  const n = index + 1;

  function onTypeChange(next: QuestionType) {
    setValue(`questions.${index}.correctIndex`, 0);
    if (next === "true_false") options.replace([{ text: "True" }, { text: "False" }]);
    else if (next === "mcq") options.replace([{ text: "" }, { text: "" }]);
    else options.replace([]);
  }

  function removeOption(position: number) {
    options.remove(position);
    const next = position < correct ? correct - 1 : position === correct ? 0 : correct;
    setValue(`questions.${index}.correctIndex`, next, { shouldDirty: true });
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Question {n}</h3>
          <div className="flex gap-1">
            <Button type="button" variant="ghost" size="sm" disabled={index === 0} onClick={() => onMove(index - 1)}>
              <ArrowUp aria-hidden="true" />
              <span className="sr-only">Move question {n} up</span>
            </Button>
            <Button type="button" variant="ghost" size="sm" disabled={index === total - 1} onClick={() => onMove(index + 1)}>
              <ArrowDown aria-hidden="true" />
              <span className="sr-only">Move question {n} down</span>
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
              <Trash2 aria-hidden="true" />
              <span className="sr-only">Delete question {n}</span>
            </Button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <div className="space-y-2">
            <Label htmlFor={`q${index}-type`}>Type</Label>
            <select
              id={`q${index}-type`}
              className={SELECT_CLASS}
              {...register(`questions.${index}.type`, { onChange: (e) => onTypeChange(e.target.value as QuestionType) })}
            >
              {(Object.keys(TYPE_LABEL) as QuestionType[]).map((value) => (
                <option key={value} value={value}>{TYPE_LABEL[value]}</option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`q${index}-points`}>Points</Label>
            <Input
              id={`q${index}-points`}
              inputMode="decimal"
              autoComplete="off"
              aria-invalid={qErr?.points ? true : undefined}
              {...register(`questions.${index}.points`)}
            />
          </div>
        </div>
        {qErr?.points ? <p role="alert" className="-mt-2 text-sm text-destructive">{qErr.points.message}</p> : null}

        <div className="space-y-2">
          <Label htmlFor={`q${index}-prompt`}>Question</Label>
          <Textarea
            id={`q${index}-prompt`}
            rows={2}
            aria-invalid={qErr?.prompt ? true : undefined}
            {...register(`questions.${index}.prompt`)}
          />
          {qErr?.prompt ? <p role="alert" className="text-sm text-destructive">{qErr.prompt.message}</p> : null}
        </div>

        {type === "true_false" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Correct answer</legend>
            {["True", "False"].map((label, value) => (
              <label key={label} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={`q${index}-correct`}
                  className="h-4 w-4 accent-primary"
                  checked={correct === value}
                  onChange={() => setValue(`questions.${index}.correctIndex`, value, { shouldDirty: true })}
                />
                {label}
              </label>
            ))}
          </fieldset>
        ) : null}

        {type === "mcq" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Options (select the correct one)</legend>
            {options.fields.map((field, position) => {
              const optionError = qErr?.options?.[position]?.text?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`q${index}-correct`}
                      className="h-4 w-4 shrink-0 accent-primary"
                      aria-label={`Mark option ${position + 1} of question ${n} as correct`}
                      checked={correct === position}
                      onChange={() => setValue(`questions.${index}.correctIndex`, position, { shouldDirty: true, shouldValidate: true })}
                    />
                    <Input
                      aria-label={`Question ${n}, option ${position + 1}`}
                      aria-invalid={optionError ? true : undefined}
                      autoComplete="off"
                      {...register(`questions.${index}.options.${position}.text`)}
                    />
                    <Button type="button" variant="ghost" size="sm" disabled={options.fields.length <= 2} onClick={() => removeOption(position)}>
                      <Trash2 aria-hidden="true" />
                      <span className="sr-only">Remove option {position + 1}</span>
                    </Button>
                  </div>
                  {optionError ? <p role="alert" className="ml-6 text-sm text-destructive">{optionError}</p> : null}
                </div>
              );
            })}
            <Button type="button" variant="outline" size="sm" disabled={options.fields.length >= MAX_OPTIONS} onClick={() => options.append({ text: "" }, { shouldFocus: true })}>
              <Plus aria-hidden="true" />
              Add option
            </Button>
          </fieldset>
        ) : null}

        {type === "short_answer" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Accepted answers (optional)</legend>
            <p className="text-xs text-muted-foreground">
              Matching ignores case and extra spaces. Leave empty to grade this question by hand.
            </p>
            {options.fields.map((field, position) => {
              const optionError = qErr?.options?.[position]?.text?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Input
                      aria-label={`Question ${n}, accepted answer ${position + 1}`}
                      aria-invalid={optionError ? true : undefined}
                      autoComplete="off"
                      {...register(`questions.${index}.options.${position}.text`)}
                    />
                    <Button type="button" variant="ghost" size="sm" onClick={() => options.remove(position)}>
                      <Trash2 aria-hidden="true" />
                      <span className="sr-only">Remove accepted answer {position + 1}</span>
                    </Button>
                  </div>
                  {optionError ? <p role="alert" className="text-sm text-destructive">{optionError}</p> : null}
                </div>
              );
            })}
            <Button type="button" variant="outline" size="sm" disabled={options.fields.length >= MAX_OPTIONS} onClick={() => options.append({ text: "" }, { shouldFocus: true })}>
              <Plus aria-hidden="true" />
              Add accepted answer
            </Button>
          </fieldset>
        ) : null}

        {arrayError(qErr?.options) ? <p role="alert" className="text-sm text-destructive">{arrayError(qErr?.options)}</p> : null}
        {qErr?.correctIndex ? <p role="alert" className="text-sm text-destructive">{qErr.correctIndex.message}</p> : null}
      </CardContent>
    </Card>
  );
}
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { FormProvider, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { QuestionEditor } from "@/features/quizzes/components/QuestionEditor";
import { useCreateQuiz } from "@/features/quizzes/hooks";
import {
  MAX_QUESTIONS,
  newQuestion,
  quizFormSchema,
  toPayload,
  type QuizFormValues,
} from "@/features/quizzes/schemas";
import { arrayError } from "@/lib/forms";
import { formatPoints } from "@/lib/format";
import type { Classroom } from "@/types";

export function QuizBuilder({ classroom }: { classroom: Classroom }) {
  const navigate = useNavigate();
  const create = useCreateQuiz(classroom.id);
  const form = useForm<QuizFormValues>({
    resolver: zodResolver(quizFormSchema),
    defaultValues: {
      title: "",
      description: "",
      minutes: "",
      due: "",
      allowRetake: false,
      publish: false,
      questions: [newQuestion()],
    },
  });
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = form;
  const questions = useFieldArray({ control, name: "questions" });
  const watched = useWatch({ control, name: "questions" });
  const total = (watched ?? []).reduce((sum, q) => sum + (Number(q?.points) || 0), 0);

  const onValid = handleSubmit((values) => {
    create.mutate(toPayload(values), {
      onSuccess: (quiz) => navigate(`/classes/${classroom.id}/quizzes/${quiz.id}`),
    });
  });

  return (
    <FormProvider {...form}>
      <form onSubmit={(e) => void onValid(e)} noValidate className="mx-auto max-w-3xl space-y-6">
        <header>
          <h2 className="text-2xl font-semibold tracking-tight">Create a quiz</h2>
          <p className="text-sm text-muted-foreground">
            Multiple-choice and true/false questions are graded automatically; short answers too, when you list accepted answers.
          </p>
        </header>

        <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />

        <TextField id="quiz-title" label="Title" required autoComplete="off" {...register("title")} error={errors.title?.message} />
        <TextAreaField id="quiz-description" label="Description" rows={3} {...register("description")} error={errors.description?.message} />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id="quiz-minutes"
            label="Time limit (minutes)"
            inputMode="numeric"
            autoComplete="off"
            hint="Leave empty for no time limit."
            {...register("minutes")}
            error={errors.minutes?.message}
          />
          <TextField id="quiz-due" label="Due date" type="datetime-local" {...register("due")} error={errors.due?.message} />
        </div>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" {...register("allowRetake")} />
            Allow students to retake the quiz
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" {...register("publish")} />
            Publish now (students see it and get it on their to-do list)
          </label>
        </div>

        <section aria-labelledby="questions-title" className="space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="questions-title" className="text-lg font-semibold">Questions</h3>
            <p className="text-sm text-muted-foreground">
              {questions.fields.length} question{questions.fields.length === 1 ? "" : "s"} · {formatPoints(total)} points in total
            </p>
          </div>
          {arrayError(errors.questions) ? (
            <p role="alert" className="text-sm text-destructive">{arrayError(errors.questions)}</p>
          ) : null}

          {questions.fields.map((field, index) => (
            <QuestionEditor
              key={field.id}
              index={index}
              total={questions.fields.length}
              onRemove={() => questions.remove(index)}
              onMove={(to) => questions.move(index, to)}
            />
          ))}

          <Button
            type="button"
            variant="outline"
            disabled={questions.fields.length >= MAX_QUESTIONS}
            onClick={() => questions.append(newQuestion(), { shouldFocus: false })}
          >
            <Plus aria-hidden="true" />
            Add question
          </Button>
        </section>

        <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
          <Button asChild variant="outline">
            <Link to={`/classes/${classroom.id}/classwork`}>Cancel</Link>
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Save quiz"}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}
import { Link } from "react-router-dom";

import { useClassroomContext } from "@/features/classrooms/context";
import { QuizBuilder } from "@/features/quizzes/components/QuizBuilder";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function QuizBuilderPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`New quiz · ${classroom.name}`);

  if (classroom.my_role !== "teacher" || classroom.is_archived) {
    return (
      <div role="alert" className="space-y-2 py-6">
        <h2 className="text-xl font-semibold">You cannot create quizzes here</h2>
        <p className="text-muted-foreground">
          {classroom.is_archived ? "This class is archived and read-only." : "Only teachers of this class can create quizzes."}
        </p>
        <Link to={`/classes/${classroom.id}/classwork`} className="text-primary underline-offset-4 hover:underline">
          Back to classwork
        </Link>
      </div>
    );
  }
  return <QuizBuilder classroom={classroom} />;
}
import { Plus } from "lucide-react";
import { Link } from "react-router-dom";

import { AsyncList } from "@/components/common/AsyncList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, QuizSummary } from "@/types";

function QuizItem({ quiz, classroomId }: { quiz: QuizSummary; classroomId: string }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">
              <Link
                to={`/classes/${classroomId}/quizzes/${quiz.id}`}
                className="underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {quiz.title}
              </Link>
            </h3>
            <p className="text-sm text-muted-foreground">
              {quiz.due_at ? (
                <>Due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time></>
              ) : (
                "No due date"
              )}
              {" · "}
              {quiz.time_limit_minutes ? `${quiz.time_limit_minutes} min` : "Untimed"}
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            {!quiz.published ? <Badge variant="outline">Draft</Badge> : null}
            {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
          </div>
        </div>
        {quiz.description ? (
          <p className="line-clamp-2 whitespace-pre-wrap break-words text-sm">{quiz.description}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function QuizzesSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useQuizzes(classroom.id);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="quizzes-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="quizzes-title" className="text-xl font-semibold">Quizzes</h2>
        {canCreate ? (
          <Button asChild>
            <Link to={`/classes/${classroom.id}/quizzes/new`}>
              <Plus aria-hidden="true" />
              Create quiz
            </Link>
          </Button>
        ) : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No quizzes yet."
        loadingLabel="Loading quizzes…"
      >
        <ul className="space-y-3">
          {data?.items.map((quiz) => (
            <li key={quiz.id}>
              <QuizItem quiz={quiz} classroomId={classroom.id} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
Quiz taking (student)
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
    seconds <= 0 ? "Time is up. Submitting your answers." : seconds <= 30 ? "30 seconds remaining." : seconds <= 60 ? "1 minute remaining." : seconds <= 300 ? "5 minutes remaining." : "";

  return (
    <div>
      <p
        role="timer"
        aria-live="off"
        aria-label="Time remaining"
        className={cn("flex items-center gap-2 font-mono text-lg font-semibold", seconds <= 60 && "text-destructive")}
      >
        <Clock className="h-5 w-5" aria-hidden="true" />
        {format(seconds)}
      </p>
      <p role="status" className="sr-only">{announcement}</p>
    </div>
  );
}
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { getErrorMessage, getStatus } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import type { AnswerInput } from "@/features/quizzes/api";
import { QuizTimer } from "@/features/quizzes/components/QuizTimer";
import { useSubmitQuiz } from "@/features/quizzes/hooks";
import { cn } from "@/lib/utils";
import type { AttemptResult, StudentQuestion, StudentQuiz } from "@/types";

export interface QuizSession {
  attemptId: string;
  expiresAt: string | null;
  skewMs: number;
  quiz: StudentQuiz;
}

interface Answer {
  optionId?: string;
  text?: string;
}
type Answers = Record<string, Answer>;

const storageKey = (attemptId: string) => `educonnect.quiz.${attemptId}`;

function loadAnswers(attemptId: string): Answers {
  try {
    const parsed: unknown = JSON.parse(sessionStorage.getItem(storageKey(attemptId)) ?? "null");
    return parsed && typeof parsed === "object" ? (parsed as Answers) : {};
  } catch {
    return {};
  }
}

function isAnswered(question: StudentQuestion, answer: Answer | undefined): boolean {
  if (!answer) return false;
  return question.type === "short_answer" ? Boolean(answer.text?.trim()) : Boolean(answer.optionId);
}

function toPayload(questions: StudentQuestion[], answers: Answers): AnswerInput[] {
  return questions.flatMap((q): AnswerInput[] => {
    const answer = answers[q.id];
    if (!isAnswered(q, answer)) return [];
    return q.type === "short_answer"
      ? [{ question_id: q.id, answer_text: answer?.text?.trim() }]
      : [{ question_id: q.id, selected_option_id: answer?.optionId }];
  });
}

function QuestionView({
  question,
  number,
  total,
  answer,
  disabled,
  onChange,
}: {
  question: StudentQuestion;
  number: number;
  total: number;
  answer: Answer | undefined;
  disabled: boolean;
  onChange: (next: Answer) => void;
}) {
  return (
    <fieldset disabled={disabled} className="space-y-4">
      <legend className="space-y-1">
        <span className="block text-sm text-muted-foreground">
          Question {number} of {total} · {question.points} point{question.points === 1 ? "" : "s"}
        </span>
        <span className="block whitespace-pre-wrap break-words text-lg font-medium">{question.prompt}</span>
      </legend>

      {question.type === "short_answer" ? (
        <Textarea
          aria-label={`Your answer to question ${number}`}
          rows={4}
          maxLength={5000}
          value={answer?.text ?? ""}
          onChange={(e) => onChange({ text: e.target.value })}
        />
      ) : (
        <div className="space-y-2">
          {question.options.map((option) => (
            <label
              key={option.id}
              className={cn(
                "flex cursor-pointer items-start gap-3 rounded-lg border p-3 text-sm transition-colors hover:bg-accent/50 focus-within:ring-2 focus-within:ring-ring",
                answer?.optionId === option.id && "border-primary bg-primary/5",
              )}
            >
              <input
                type="radio"
                name={`question-${question.id}`}
                className="mt-0.5 h-4 w-4 accent-primary"
                checked={answer?.optionId === option.id}
                onChange={() => onChange({ optionId: option.id })}
              />
              <span className="break-words">{option.text}</span>
            </label>
          ))}
        </div>
      )}
    </fieldset>
  );
}

interface QuizTakerProps {
  session: QuizSession;
  onSubmitted: (result: AttemptResult) => void;
  /** Leave the attempt screen without a result (e.g. the time limit passed). */
  onAbort: () => void;
}

export function QuizTaker({ session, onSubmitted, onAbort }: QuizTakerProps) {
  const { quiz, attemptId } = session;
  const questions = quiz.questions;
  const { mutate, isPending, isError, error } = useSubmitQuiz(quiz.id);

  const [answers, setAnswers] = useState<Answers>(() => loadAnswers(attemptId));
  const [index, setIndex] = useState(0);
  const answersRef = useRef(answers);
  answersRef.current = answers;
  const sentRef = useRef(false);

  // Keep answers across a page refresh (the open attempt resumes through /start).
  useEffect(() => {
    try {
      sessionStorage.setItem(storageKey(attemptId), JSON.stringify(answers));
    } catch {
      /* storage blocked: answers just will not survive a reload */
    }
  }, [answers, attemptId]);

  // Warn before leaving the page while the attempt is running.
  useEffect(() => {
    const handler = (event: BeforeUnloadEvent) => {
      if (sentRef.current) return;
      event.preventDefault();
      event.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, []);

  const send = useCallback(() => {
    if (sentRef.current) return;
    sentRef.current = true;
    mutate(toPayload(questions, answersRef.current), {
      onSuccess: (result) => {
        try {
          sessionStorage.removeItem(storageKey(attemptId));
        } catch {
          /* ignore */
        }
        onSubmitted(result);
      },
      onError: () => {
        sentRef.current = false;
      },
    });
  }, [mutate, questions, attemptId, onSubmitted]);

  function onSubmitClick() {
    const unanswered = questions.filter((q) => !isAnswered(q, answers[q.id])).length;
    if (unanswered > 0) {
      const ok = window.confirm(`You have ${unanswered} unanswered question${unanswered === 1 ? "" : "s"}. Submit anyway?`);
      if (!ok) return;
    }
    send();
  }

  const question = questions[index];
  if (!question) {
    return <p className="text-muted-foreground">This quiz has no questions.</p>;
  }
  const answeredCount = questions.filter((q) => isAnswered(q, answers[q.id])).length;
  const timeIsUp = isError && getStatus(error) === 409;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border p-4">
        <div>
          <h2 className="text-lg font-semibold">{quiz.title}</h2>
          <p className="text-sm text-muted-foreground">{answeredCount} of {questions.length} answered</p>
        </div>
        {session.expiresAt ? (
          <QuizTimer expiresAt={session.expiresAt} skewMs={session.skewMs} onExpire={send} />
        ) : (
          <p className="text-sm text-muted-foreground">No time limit</p>
        )}
      </div>

      <ErrorAlert message={isError ? getErrorMessage(error) : null} />
      {timeIsUp ? (
        <Button variant="outline" onClick={onAbort}>Back to the quiz page</Button>
      ) : null}

      <div className="grid gap-6 md:grid-cols-[1fr_14rem]">
        <div className="space-y-6">
          <QuestionView
            key={question.id}
            question={question}
            number={index + 1}
            total={questions.length}
            answer={answers[question.id]}
            disabled={isPending}
            onChange={(next) => setAnswers((current) => ({ ...current, [question.id]: next }))}
          />
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Button type="button" variant="outline" disabled={index === 0} onClick={() => setIndex(index - 1)}>
              <ChevronLeft aria-hidden="true" />
              Previous
            </Button>
            {index < questions.length - 1 ? (
              <Button type="button" variant="outline" onClick={() => setIndex(index + 1)}>
                Next
                <ChevronRight aria-hidden="true" />
              </Button>
            ) : (
              <Button type="button" disabled={isPending} onClick={onSubmitClick}>
                {isPending ? "Submitting…" : "Submit quiz"}
              </Button>
            )}
          </div>
        </div>

        <nav aria-label="Question navigator" className="space-y-3">
          <ol className="grid grid-cols-5 gap-2 md:grid-cols-4">
            {questions.map((q, i) => {
              const answered = isAnswered(q, answers[q.id]);
              return (
                <li key={q.id}>
                  <button
                    type="button"
                    aria-label={`Question ${i + 1}, ${answered ? "answered" : "not answered"}`}
                    aria-current={i === index ? "step" : undefined}
                    onClick={() => setIndex(i)}
                    className={cn(
                      "h-10 w-full rounded-md border text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                      answered ? "border-primary bg-primary/10 text-primary" : "text-muted-foreground",
                      i === index && "ring-2 ring-primary",
                    )}
                  >
                    {i + 1}
                  </button>
                </li>
              );
            })}
          </ol>
          <Button type="button" className="w-full" disabled={isPending} onClick={onSubmitClick}>
            {isPending ? "Submitting…" : "Submit quiz"}
          </Button>
        </nav>
      </div>
    </div>
  );
}
import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AttemptResult, StudentQuiz } from "@/types";

interface QuizResultViewProps {
  quiz: StudentQuiz;
  attempt: AttemptResult;
  onClose: () => void;
}

/** Per-question outcome. The answer key is never shown (the API does not send it). */
export function QuizResultView({ quiz, attempt, onClose }: QuizResultViewProps) {
  const byQuestion = new Map(attempt.answers.map((a) => [a.question_id, a]));
  const hasScore = attempt.score !== null && attempt.max_score !== null;

  return (
    <section aria-labelledby="result-title" className="space-y-6">
      <header className="space-y-2 rounded-lg border p-4">
        <h2 id="result-title" className="text-lg font-semibold">Your result: {quiz.title}</h2>
        {hasScore ? (
          <p className="text-3xl font-semibold">
            {formatPoints(attempt.score as number)}
            <span className="text-lg font-normal text-muted-foreground"> / {formatPoints(attempt.max_score as number)}</span>
          </p>
        ) : null}
        {attempt.pending_manual_grading ? (
          <p role="note" className="text-sm text-muted-foreground">
            Some answers are waiting for your teacher to grade them. Your score may go up.
          </p>
        ) : null}
        {attempt.submitted_at ? (
          <p className="text-sm text-muted-foreground">
            Submitted <time dateTime={attempt.submitted_at}>{formatDateTime(attempt.submitted_at)}</time>
          </p>
        ) : null}
      </header>

      {attempt.answers.length === 0 ? (
        <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
          No answers were recorded for this attempt (it was closed when the time limit ran out).
        </p>
      ) : (
        <ol className="space-y-3">
          {quiz.questions.map((question, i) => {
            const answer = byQuestion.get(question.id);
            const chosen = answer?.selected_option_id
              ? question.options.find((o) => o.id === answer.selected_option_id)?.text
              : answer?.answer_text;
            const state = answer?.is_correct === true ? "correct" : answer?.is_correct === false ? "incorrect" : "pending";
            return (
              <li key={question.id} className="space-y-2 rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium">
                    <span className="text-muted-foreground">{i + 1}. </span>
                    {question.prompt}
                  </p>
                  <p className="flex items-center gap-1 whitespace-nowrap text-sm">
                    {state === "correct" ? (
                      <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
                    ) : state === "incorrect" ? (
                      <XCircle className="h-4 w-4 text-destructive" aria-hidden="true" />
                    ) : (
                      <CircleHelp className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                    )}
                    <span>
                      {state === "correct" ? "Correct" : state === "incorrect" ? "Incorrect" : "Awaiting grading"}
                      {" · "}
                      {answer?.points_awarded !== null && answer?.points_awarded !== undefined ? formatPoints(answer.points_awarded) : "—"}
                      {" / "}
                      {formatPoints(question.points)}
                    </span>
                  </p>
                </div>
                <p className="text-sm">
                  <span className="text-muted-foreground">Your answer: </span>
                  {chosen ? <span className="whitespace-pre-wrap break-words">{chosen}</span> : <span className="italic">No answer</span>}
                </p>
              </li>
            );
          })}
        </ol>
      )}

      <Button type="button" variant="outline" onClick={onClose}>Done</Button>
    </section>
  );
}
import { useCallback, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QuizResultView } from "@/features/quizzes/components/QuizResultView";
import { QuizTaker, type QuizSession } from "@/features/quizzes/components/QuizTaker";
import { useMyAttempt, useStartQuiz } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AttemptResult, Classroom, StudentQuiz } from "@/types";

export function StudentQuizView({ quiz, classroom }: { quiz: StudentQuiz; classroom: Classroom }) {
  const mine = useMyAttempt(quiz.id);
  const start = useStartQuiz(quiz.id);
  const [session, setSession] = useState<QuizSession | null>(null);
  const [result, setResult] = useState<AttemptResult | null>(null);

  const onSubmitted = useCallback((attempt: AttemptResult) => {
    setSession(null);
    setResult(attempt);
  }, []);
  const onAbort = useCallback(() => {
    setSession(null);
    void mine.refetch();
  }, [mine]);

  if (session) return <QuizTaker session={session} onSubmitted={onSubmitted} onAbort={onAbort} />;
  if (result) return <QuizResultView quiz={quiz} attempt={result} onClose={() => setResult(null)} />;

  const info = mine.data;
  const attempt = info?.attempt ?? null;
  const open = attempt !== null && attempt.submitted_at === null;
  const finished = attempt !== null && attempt.submitted_at !== null;

  function onStart() {
    start.mutate(undefined, {
      onSuccess: ({ attempt: started, serverNow }) =>
        setSession({
          attemptId: started.attempt_id,
          expiresAt: started.expires_at,
          skewMs: serverNow === null ? 0 : serverNow - Date.now(),
          quiz: started.quiz,
        }),
    });
  }

  return (
    <article className="mx-auto max-w-3xl space-y-6">
      <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to classwork
      </Link>

      <header className="space-y-2">
        <h2 className="break-words text-2xl font-semibold tracking-tight">{quiz.title}</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <span>{quiz.questions.length} question{quiz.questions.length === 1 ? "" : "s"}</span>
          <span aria-hidden="true">·</span>
          <span>{quiz.time_limit_minutes ? `${quiz.time_limit_minutes} minutes` : "No time limit"}</span>
          {quiz.due_at ? (
            <>
              <span aria-hidden="true">·</span>
              <span>Due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time></span>
            </>
          ) : null}
          {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
        </div>
        {quiz.description ? <p className="whitespace-pre-wrap break-words">{quiz.description}</p> : null}
      </header>

      {mine.isPending ? <Spinner label="Loading your attempts…" /> : null}
      {mine.isError ? (
        <div className="space-y-3">
          <ErrorAlert message={getErrorMessage(mine.error)} />
          <Button variant="outline" size="sm" onClick={() => void mine.refetch()}>Try again</Button>
        </div>
      ) : null}

      {info ? (
        <section aria-label="Your attempts" className="space-y-4 rounded-lg border p-4">
          {finished && attempt ? (
            <div className="space-y-1">
              <p className="font-medium">
                Last attempt:{" "}
                {attempt.score !== null && attempt.max_score !== null
                  ? `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`
                  : "submitted"}
                {attempt.pending_manual_grading ? " (some answers await grading)" : ""}
              </p>
              <Button variant="outline" size="sm" onClick={() => setResult(attempt)}>Review last attempt</Button>
            </div>
          ) : null}
          {open && quiz.time_limit_minutes ? (
            <p role="note" className="text-sm text-muted-foreground">
              You have an attempt in progress. Its timer keeps running while you are away.
            </p>
          ) : null}
          {!info.can_start && info.attempts_used > 0 && !open ? (
            <p className="text-sm text-muted-foreground">
              {classroom.is_archived ? "This class is archived." : "You have completed this quiz. Retakes are not allowed."}
            </p>
          ) : null}

          <ErrorAlert message={start.isError ? getErrorMessage(start.error) : null} />
          {info.can_start ? (
            <Button disabled={start.isPending} onClick={onStart}>
              {start.isPending ? "Starting…" : open ? "Resume quiz" : info.attempts_used > 0 ? "Retake quiz" : "Start quiz"}
            </Button>
          ) : null}
          {info.attempts_used > 0 ? (
            <p className="text-xs text-muted-foreground">Attempts used: {info.attempts_used}</p>
          ) : null}
        </section>
      ) : null}
    </article>
  );
}
Quiz overview and results (teacher)
import { zodResolver } from "@hookform/resolvers/zod";
import { Fragment, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RESULTS_PAGE_SIZE, useGradeAnswer, useQuizResultsPage } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { AnswerResult, AttemptResult, TeacherQuestion, TeacherQuiz } from "@/types";

function ManualGradeForm({
  quizId,
  attemptId,
  question,
  disabled,
}: {
  quizId: string;
  attemptId: string;
  question: TeacherQuestion;
  disabled: boolean;
}) {
  const grade = useGradeAnswer(quizId);
  const schema = useMemo(
    () =>
      z.object({
        points: z
          .string()
          .trim()
          .regex(/^\d+(\.\d{1,2})?$/, "Enter a number (up to 2 decimals).")
          .refine((v) => Number(v) <= question.points, `At most ${formatPoints(question.points)}.`),
      }),
    [question.points],
  );
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<{ points: string }>({ resolver: zodResolver(schema), defaultValues: { points: "" } });

  const submit = handleSubmit(({ points }) =>
    grade.mutate({ attemptId, questionId: question.id, points: Number(points) }),
  );

  return (
    <form onSubmit={(e) => void submit(e)} noValidate className="mt-2 flex flex-wrap items-start gap-2">
      <div>
        <Input
          aria-label="Points to award"
          inputMode="decimal"
          autoComplete="off"
          className="w-24"
          disabled={disabled || grade.isPending}
          aria-invalid={errors.points ? true : undefined}
          {...register("points")}
        />
        {errors.points ? <p role="alert" className="mt-1 text-xs text-destructive">{errors.points.message}</p> : null}
      </div>
      <span className="pt-2 text-sm text-muted-foreground">/ {formatPoints(question.points)}</span>
      <Button type="submit" size="sm" disabled={disabled || grade.isPending}>
        {grade.isPending ? "Saving…" : "Save points"}
      </Button>
      <ErrorAlert className="basis-full" message={grade.isError ? getErrorMessage(grade.error) : null} />
    </form>
  );
}

function AttemptReview({ quiz, attempt, readOnly }: { quiz: TeacherQuiz; attempt: AttemptResult; readOnly: boolean }) {
  if (attempt.answers.length === 0) {
    return <p className="text-sm text-muted-foreground">No answers were recorded for this attempt.</p>;
  }
  const byQuestion = new Map<string, AnswerResult>(attempt.answers.map((a) => [a.question_id, a]));
  return (
    <ol className="space-y-3">
      {quiz.questions.map((question, i) => {
        const answer = byQuestion.get(question.id);
        const chosen = answer?.selected_option_id
          ? question.options.find((o) => o.id === answer.selected_option_id)?.text
          : answer?.answer_text;
        const pending = answer !== undefined && answer.is_correct === null;
        return (
          <li key={question.id} className="rounded-md border bg-background p-3 text-sm">
            <p className="font-medium">
              <span className="text-muted-foreground">{i + 1}. </span>
              {question.prompt}
            </p>
            <p className="mt-1">
              <span className="text-muted-foreground">Answer: </span>
              {chosen ? <span className="whitespace-pre-wrap break-words">{chosen}</span> : <span className="italic">No answer</span>}
            </p>
            <p className="text-muted-foreground">
              {pending
                ? "Awaiting your grade"
                : `${answer?.points_awarded !== null && answer?.points_awarded !== undefined ? formatPoints(answer.points_awarded) : "0"} / ${formatPoints(question.points)} points`}
            </p>
            {pending ? (
              <ManualGradeForm quizId={quiz.id} attemptId={attempt.id} question={question} disabled={readOnly} />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export function QuizResultsTable({ quiz, readOnly }: { quiz: TeacherQuiz; readOnly: boolean }) {
  const [offset, setOffset] = useState(0);
  const [openId, setOpenId] = useState<string | null>(null);
  const query = useQuizResultsPage(quiz.id, offset);
  const data = query.data;

  return (
    <section aria-labelledby="results-title" className="space-y-3">
      <h2 id="results-title" className="text-xl font-semibold">Results</h2>

      {data ? (
        <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Submitted", String(data.submitted_count)],
            ["Not attempted", String(data.not_attempted_count)],
            ["Attempts", String(data.attempt_count)],
            ["Average (best attempts)", data.average_score === null ? "—" : `${formatPoints(data.average_score)} / ${formatPoints(data.max_score)}`],
          ].map(([term, value]) => (
            <div key={term} className="rounded-lg border p-3">
              <dt className="text-xs text-muted-foreground">{term}</dt>
              <dd className="text-lg font-semibold">{value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={data?.attempts.length === 0 && offset === 0}
        emptyText="Nobody has started this quiz yet."
        loadingLabel="Loading results…"
      >
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Attempts and scores for {quiz.title}</caption>
            <thead className="bg-muted/50 text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-2 font-medium">Student</th>
                <th scope="col" className="px-4 py-2 font-medium">Started</th>
                <th scope="col" className="px-4 py-2 font-medium">Status</th>
                <th scope="col" className="px-4 py-2 text-right font-medium">Score</th>
                <th scope="col" className="px-4 py-2 font-medium"><span className="sr-only">Review</span></th>
              </tr>
            </thead>
            <tbody className="divide-y">
              {data?.attempts.map((attempt) => {
                const name = attempt.student?.full_name ?? "Unknown student";
                const expanded = openId === attempt.id;
                return (
                  <Fragment key={attempt.id}>
                    <tr>
                      <th scope="row" className="px-4 py-3 font-medium">{name}</th>
                      <td className="whitespace-nowrap px-4 py-3">
                        <time dateTime={attempt.started_at}>{formatDateTime(attempt.started_at)}</time>
                      </td>
                      <td className="px-4 py-3">
                        {attempt.submitted_at === null ? (
                          <Badge variant="outline">In progress</Badge>
                        ) : attempt.pending_manual_grading ? (
                          <Badge variant="secondary">Needs grading</Badge>
                        ) : (
                          <Badge>Submitted</Badge>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">
                        {attempt.score !== null && attempt.max_score !== null
                          ? `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`
                          : "—"}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          aria-expanded={expanded}
                          onClick={() => setOpenId(expanded ? null : attempt.id)}
                        >
                          {expanded ? "Hide" : "Review"}
                          <span className="sr-only"> answers of {name}</span>
                        </Button>
                      </td>
                    </tr>
                    {expanded ? (
                      <tr>
                        <td colSpan={5} className="bg-muted/30 px-4 py-4">
                          <AttemptReview quiz={quiz} attempt={attempt} readOnly={readOnly} />
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        </div>
        {data && data.attempt_count > RESULTS_PAGE_SIZE ? (
          <div className="flex items-center justify-between">
            <Button variant="outline" size="sm" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - RESULTS_PAGE_SIZE))}>
              Previous
            </Button>
            <p className="text-sm text-muted-foreground">
              {offset + 1}–{Math.min(offset + RESULTS_PAGE_SIZE, data.attempt_count)} of {data.attempt_count}
            </p>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + RESULTS_PAGE_SIZE >= data.attempt_count}
              onClick={() => setOffset(offset + RESULTS_PAGE_SIZE)}
            >
              Next
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
import { Check } from "lucide-react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { QuizResultsTable } from "@/features/quizzes/components/QuizResultsTable";
import { useUpdateQuiz } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";
import type { Classroom, TeacherQuiz } from "@/types";

const TYPE_LABEL = { mcq: "Multiple choice", true_false: "True / False", short_answer: "Short answer" } as const;

export function TeacherQuizView({ quiz, classroom }: { quiz: TeacherQuiz; classroom: Classroom }) {
  const update = useUpdateQuiz(quiz.id);
  const readOnly = classroom.is_archived;
  const total = quiz.questions.reduce((sum, q) => sum + q.points, 0);

  return (
    <article className="mx-auto max-w-4xl space-y-8">
      <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
        ← Back to classwork
      </Link>

      <header className="space-y-2">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <h2 className="break-words text-2xl font-semibold tracking-tight">{quiz.title}</h2>
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant={quiz.published ? "default" : "outline"}>{quiz.published ? "Published" : "Draft"}</Badge>
            {quiz.allow_retake ? <Badge>Retakes allowed</Badge> : null}
            {!readOnly ? (
              <Button
                size="sm"
                variant={quiz.published ? "outline" : "default"}
                disabled={update.isPending}
                onClick={() => update.mutate(!quiz.published)}
              >
                {update.isPending ? "Saving…" : quiz.published ? "Unpublish" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {quiz.questions.length} question{quiz.questions.length === 1 ? "" : "s"} · {formatPoints(total)} points ·{" "}
          {quiz.time_limit_minutes ? `${quiz.time_limit_minutes} min` : "untimed"}
          {quiz.due_at ? <> · due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time></> : null}
        </p>
        {quiz.description ? <p className="whitespace-pre-wrap break-words">{quiz.description}</p> : null}
        <ErrorAlert message={update.isError ? getErrorMessage(update.error) : null} />
      </header>

      <section aria-labelledby="questions-title" className="space-y-3">
        <h2 id="questions-title" className="text-xl font-semibold">Questions</h2>
        {quiz.questions.length === 0 ? (
          <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">
            This quiz has no questions, so it cannot be published.
          </p>
        ) : (
          <ol className="space-y-3">
            {quiz.questions.map((question, i) => (
              <li key={question.id} className="space-y-2 rounded-lg border p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <p className="font-medium">
                    <span className="text-muted-foreground">{i + 1}. </span>
                    {question.prompt}
                  </p>
                  <p className="whitespace-nowrap text-sm text-muted-foreground">
                    {TYPE_LABEL[question.type]} · {formatPoints(question.points)} pt
                  </p>
                </div>
                {question.options.length > 0 ? (
                  <ul className="space-y-1 text-sm">
                    {question.options.map((option) => (
                      <li key={option.id} className="flex items-center gap-2">
                        {option.is_correct ? (
                          <>
                            <Check className="h-4 w-4 text-primary" aria-hidden="true" />
                            <span className="sr-only">Correct: </span>
                          </>
                        ) : (
                          <span className="inline-block h-4 w-4" aria-hidden="true" />
                        )}
                        <span className={option.is_correct ? "font-medium" : undefined}>{option.text}</span>
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="text-sm italic text-muted-foreground">Graded by hand.</p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>

      {quiz.published || quiz.questions.length > 0 ? <QuizResultsTable quiz={quiz} readOnly={readOnly} /> : null}
    </article>
  );
}
import { Link, useParams } from "react-router-dom";

import { getStatus } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";
import { useClassroomContext } from "@/features/classrooms/context";
import { StudentQuizView } from "@/features/quizzes/components/StudentQuizView";
import { TeacherQuizView } from "@/features/quizzes/components/TeacherQuizView";
import { useQuiz } from "@/features/quizzes/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function QuizPage() {
  const { classroom } = useClassroomContext();
  const { quizId = "" } = useParams();
  const { data: quiz, isPending, error, refetch } = useQuiz(quizId);
  useDocumentTitle(quiz ? `${quiz.title} · ${classroom.name}` : classroom.name);

  if (isPending) return <Spinner label="Loading quiz…" />;

  if (error || !quiz || quiz.classroom_id !== classroom.id) {
    const missing = !error || getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="space-y-3 py-6">
        <Link to={`/classes/${classroom.id}/classwork`} className="text-sm text-muted-foreground hover:text-foreground">
          ← Back to classwork
        </Link>
        <h2 className="text-xl font-semibold">{missing ? "Quiz not found" : "Could not load this quiz"}</h2>
        {!missing ? <Button variant="outline" size="sm" onClick={() => void refetch()}>Try again</Button> : null}
      </div>
    );
  }

  return quiz.view === "teacher" ? (
    <TeacherQuizView quiz={quiz} classroom={classroom} />
  ) : (
    <StudentQuizView quiz={quiz} classroom={classroom} />
  );
}
Tabs and router
import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { suffix: "", label: "Stream", end: true },
  { suffix: "/classwork", label: "Classwork", end: false },
  { suffix: "/people", label: "People", end: false },
  { suffix: "/grades", label: "Grades", end: false },
];

/** Assignment and quiz pages live under the Classwork tab, so it stays highlighted there. */
const CLASSWORK_DETAIL = /\/(assignments|quizzes)(\/|$)/;

export function ClassroomTabs({ classroomId }: { classroomId: string }) {
  const base = `/classes/${classroomId}`;
  const { pathname } = useLocation();
  const inClasswork = CLASSWORK_DETAIL.test(pathname);

  return (
    <nav aria-label="Classroom sections" className="border-b">
      <ul className="-mb-px flex gap-1 overflow-x-auto">
        {TABS.map(({ suffix, label, end }) => (
          <li key={label}>
            <NavLink
              to={`${base}${suffix}`}
              end={end}
              className={({ isActive }) => {
                const active = label === "Classwork" ? isActive || inClasswork : isActive;
                return cn(
                  "block whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active ? "border-primary text-primary" : "border-transparent text-muted-foreground hover:text-foreground",
                );
              }}
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
import { createBrowserRouter, Navigate, useParams } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { AssignmentPage } from "@/pages/classroom/AssignmentPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
import { GradesPage } from "@/pages/classroom/GradesPage";
import { PeoplePage } from "@/pages/classroom/PeoplePage";
import { QuizBuilderPage } from "@/pages/classroom/QuizBuilderPage";
import { QuizPage } from "@/pages/classroom/QuizPage";
import { StreamPage } from "@/pages/classroom/StreamPage";
import { ClassesPage } from "@/pages/ClassesPage";
import { HomePage } from "@/pages/Home";
import { LoginPage } from "@/pages/Login";
import { NotFoundPage } from "@/pages/NotFoundPage";
import { ProfilePage } from "@/pages/ProfilePage";
import { RegisterPage } from "@/pages/Register";
import { TodoPage } from "@/pages/TodoPage";
import { GuestRoute } from "@/routes/GuestRoute";
import { ProtectedRoute } from "@/routes/ProtectedRoute";
import { RoleRoute } from "@/routes/RoleRoute";

/**
 * `/classrooms/:id/...` is an alias of `/classes/:id/...`. The backend puts links such as
 * `/classrooms/{cid}/assignments/{id}` in notifications and to-do items; they land here.
 */
function ClassroomsRedirect() {
  const { classroomId = "", "*": rest } = useParams();
  return <Navigate to={`/classes/${classroomId}${rest ? `/${rest}` : ""}`} replace />;
}

export const router = createBrowserRouter([
  {
    element: <GuestRoute />,
    children: [
      { path: "/login", element: <LoginPage /> },
      { path: "/register", element: <RegisterPage /> },
    ],
  },
  {
    element: <ProtectedRoute />,
    children: [
      {
        element: <AppLayout />,
        children: [
          { index: true, element: <HomePage /> },
          { path: "todo", element: <TodoPage /> },
          { path: "classes", element: <ClassesPage /> },
          { path: "profile", element: <ProfilePage /> },
          {
            element: <RoleRoute roles={["admin"]} />,
            children: [{ path: "admin", element: <AdminPage /> }],
          },
          {
            path: "classes/:classroomId",
            element: <ClassroomLayout />,
            children: [
              { index: true, element: <StreamPage /> },
              { path: "classwork", element: <ClassworkPage /> },
              { path: "people", element: <PeoplePage /> },
              { path: "grades", element: <GradesPage /> },
              { path: "assignments/:assignmentId", element: <AssignmentPage /> },
              { path: "quizzes/new", element: <QuizBuilderPage /> },
              { path: "quizzes/:quizId", element: <QuizPage /> },
            ],
          },
          { path: "classrooms/:classroomId/*", element: <ClassroomsRedirect /> },
          { path: "*", element: <NotFoundPage /> },
        ],
      },
    ],
  },
]);

How to run and test
# backend: apply the one-line Date-header edit, then restart the API
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run build        # must type-check cleanly
npm run dev
No backend tests change. The one backend edit only widens the exposed response headers.
Checklist
Use two browser profiles: teacher Tina and student Sam, with Sam in Tina's class.
Assignments, teacher
#	Do this	Expected
1	Classwork → Create assignment, submit empty	"Title is required." and focus jumps to the field
2	Points 0 or 12.5	"Enter a number from 1 to 100000." / "Enter a whole number."
3	Drop a .exe, then a 30 MB file	Red inline errors, nothing uploaded
4	Drop a pdf and a png	Progress %, then both listed with a remove button
5	Create it published	Dialog closes; the card appears. Click the title to open the assignment page
6	On the page	Instructions, due date, points, and an attachment list. The png has an inline preview, the pdf an Open button
Assignments, student
#	Do this	Expected
7	Open the assignment as Sam	"Your work" shows Assigned (or Missing if overdue)
8	Turn in with no text and no file	"Write an answer or attach at least one file."
9	Type an answer and attach a file, then Turn in	Status becomes Turned in, with the submitted time. "Your work was turned in." is announced
10	Edit and Resubmit	Same submission, updated
11	As Tina, open View work in the table	Sam's text and file (downloadable)
12	Enter grade 51 on a 50-point assignment	"At most 50."
13	Enter 45 and feedback, Save grade	Row shows Graded. Return was disabled until saved
14	As Sam, reload	Still Turned in, no grade (hidden before return)
15	As Tina, click Return	Row shows Returned. Sam sees Graded, 45 / 50 and the feedback
16	As Sam, resubmit	A note warned the grade would clear. Status returns to Turned in
17	Archive the class	Forms are disabled with a note
Quizzes, teacher
#	Do this	Expected
18	Classwork → Create quiz	Builder page with one empty MCQ
19	Save with empty prompt and options	Inline errors under the fields, and focus moves to the first
20	MCQ with two equal options	"Each option must be different."
21	Add: MCQ (mark correct), True/False, Short answer with one accepted answer, Short answer with none	The type switch resets options. The total points counter updates
22	Move a question down, delete one	Numbers re-flow
23	Tick Publish now with zero questions	"Add at least one question before publishing."
24	Set 2 minutes, allow retakes, publish, Save quiz	Redirects to the quiz page showing the answer key (check marks)
Quizzes, student
#	Do this	Expected
25	Open the quiz as Sam	Intro with question count, time limit and Start quiz
26	Click Start quiz	A countdown timer and the first question. The navigator shows 1..n
27	Answer 2 questions, jump with the navigator	Answered buttons are tinted; aria-current marks the current one
28	Refresh the page, then Resume quiz	Same attempt, same remaining time, answers restored
29	Submit with unanswered questions	Confirm: "You have N unanswered questions. Submit anyway?"
30	After submitting	Result screen: score, and per-question correct or incorrect with points. No correct answers revealed
31	Back on the intro	"Last attempt: x / y", and Retake quiz because retakes are on
32	Start a 1-minute quiz and wait	At 0:00 it auto-submits and shows the result. If the clock ran over the 10 s grace, a "time limit" message appears with a back button
33	Change your device clock by +10 min and start	The timer still starts at the full limit (it uses the server clock)
Quizzes, teacher results
#	Do this	Expected
34	Quiz page → Results	Stats (submitted, not attempted, attempts, average of best attempts) and a table
35	Review a row	The student's answers and points per question
36	For the manual short answer, enter more than its points	"At most N."
37	Enter valid points, Save points	Score updates, status leaves "Needs grading"
Troubleshooting
Problem	Fix
Cannot find module 'react-hook-form' or zod	npm install react-hook-form zod @hookform/resolvers in frontend/
Type errors mentioning AttemptResult.answers	You did not delete the two old interfaces (AttemptResult, QuizResults) before appending the new block in types/index.ts
Timer is off by the device's clock error	The Date header is not exposed. Check the expose_headers edit in main.py and restart the API
Zod resolver type errors	@hookform/resolvers must be 3.x with zod 3.x. Zod 4 needs resolvers 5
Upload error Content-Type / boundary	Do not set Content-Type yourself for FormData. The api instance does not
Image preview stays "Loading preview…"	GET /files/{id} returned 404: the viewer lacks access, or the file is not attached anywhere
422 "Attachment … not found" on submit	You attached a file you did not upload. Upload it with the dropzone
409 "Your work was graded" on resubmit	Wait for the teacher to Return the work first
Removing an attachment does not free the file	Files attached to a saved submission or assignment can't be deleted (409, ignored). They detach from the form, and the saved item is updated on the next submit
Quiz timer shows 00:00 immediately	The attempt already expired. Go back; the next start begins a new attempt if retakes are allowed
Results table is empty although students took the quiz	The table lists current students only. Students who left the class are hidden
Reply NEXT for STEP 17.


```