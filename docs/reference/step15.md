```ts
STEP 15: Classroom detail (Stream, Classwork, People, Grades)
Route. The classroom pages stay at /classes/:classroomId, because the cards and dialogs from STEPS 13-14 already link there. I added a redirect so /classrooms/:id (and /classrooms/:id/people and so on) lands on the same page.
Layout. The STEP 13 sidebar is replaced by a header (name, section/subject/room, role, join code with a copy button) and a tab bar: Stream | Classwork | People | Grades. Delete ClassroomSidebar.tsx.
Design decisions:
Teacher UI. It is based on classroom.my_role === "teacher", which the API also returns for admins. Create buttons, composers and delete buttons are hidden in archived classrooms (the API would answer 403 anyway), and a banner explains why.
Stream. 
oAnnouncements are paginated with “Load more” (useInfiniteQuery, 20 per page).
oTeachers get a composer and can delete announcements.
oComments open in a right-side drawer (sheet.tsx, built on Radix Dialog). They load only when the drawer opens. The author or a classroom teacher can delete a comment.
Classwork. 
oAssignments, Quizzes and Materials are three sections, each loading independently.
o“Create assignment” supports title, description, due date, points and publish-now. Drafts get a Publish button.
o“Create quiz” creates a draft without questions. The nested question editor comes with the quiz pages, so for now the quiz dialog only sets title, description, time limit and retakes.
oMaterials have a create dialog and teacher delete. Attachments are only counted for now, because file upload and download UI needs authenticated blob fetches (a later step).
oItems are not clickable yet: assignment, quiz and submission detail pages are the next frontend steps.
Grades. There is no grades endpoint, so the tab is assembled from existing ones. 
oStudents see one row per published assignment and quiz (my-submission, my-attempt). Scores show only after the teacher returns work, matching the backend rule.
oTeachers see per-assignment counts (turned in, to grade, graded or returned, not submitted) and per-quiz stats (submitted, not attempted, average).
oEach row costs one request, which is fine for a class’s worth of work. A single gradebook endpoint can replace this later.
Times. <input type="datetime-local"> values are converted to UTC ISO strings, because the API requires timezone-aware datetimes.
Dependencies. No new packages. @radix-ui/react-dialog came with STEP 14, and tailwindcss-animate provides the drawer animation.
Files in this step
text
frontend/src/
├── types/index.ts                                   ← EDIT    (append block)
├── lib/format.ts                                    ← NEW
├── hooks/useCopyToClipboard.ts                      ← NEW
├── routes/index.tsx                                 ← REPLACE (grades route, /classrooms redirect)
├── components/
│   ├── ui/{sheet,textarea,badge}.tsx                ← NEW
│   ├── common/{TextAreaField,AsyncList,FormDialog}.tsx ← NEW
│   └── layout/
│       ├── ClassroomLayout.tsx                      ← REPLACE (header + tabs)
│       └── ClassroomSidebar.tsx                     ← DELETE
├── features/
│   ├── classrooms/
│   │   ├── api.ts, hooks.ts                         ← REPLACE (+ people)
│   │   └── components/{ClassroomHeader,ClassroomTabs,PeopleList}.tsx ← NEW
│   ├── announcements/
│   │   ├── api.ts, hooks.ts                         ← NEW
│   │   └── components/{AnnouncementComposer,AnnouncementItem,CommentsDrawer}.tsx ← NEW
│   ├── comments/{api,hooks}.ts                      ← NEW
│   ├── assignments/{api,hooks}.ts + components/{AssignmentsSection,CreateAssignmentDialog}.tsx ← NEW
│   ├── quizzes/{api,hooks}.ts + components/{QuizzesSection,CreateQuizDialog}.tsx ← NEW
│   ├── materials/{api,hooks}.ts + components/{MaterialsSection,CreateMaterialDialog}.tsx ← NEW
│   └── grades/components/{StudentGrades,TeacherGrades}.tsx ← NEW
└── pages/classroom/{StreamPage,ClassworkPage,PeoplePage,GradesPage}.tsx ← REPLACE ×3, NEW ×1
bash
cd frontend/src
rm components/layout/ClassroomSidebar.tsx
mkdir -p features/{announcements,comments,assignments,quizzes,materials}/components features/grades/components
rm -f features/{announcements,assignments,quizzes,materials}/.gitkeep
touch lib/format.ts hooks/useCopyToClipboard.ts \
  components/ui/{sheet,textarea,badge}.tsx \
  components/common/{TextAreaField,AsyncList,FormDialog}.tsx \
  features/classrooms/components/{ClassroomHeader,ClassroomTabs,PeopleList}.tsx \
  features/announcements/{api,hooks}.ts \
  features/announcements/components/{AnnouncementComposer,AnnouncementItem,CommentsDrawer}.tsx \
  features/comments/{api,hooks}.ts \
  features/assignments/{api,hooks}.ts features/assignments/components/{AssignmentsSection,CreateAssignmentDialog}.tsx \
  features/quizzes/{api,hooks}.ts features/quizzes/components/{QuizzesSection,CreateQuizDialog}.tsx \
  features/materials/{api,hooks}.ts features/materials/components/{MaterialsSection,CreateMaterialDialog}.tsx \
  features/grades/components/{StudentGrades,TeacherGrades}.tsx \
  pages/classroom/GradesPage.tsx
Types, helpers, hook
ts
export interface UserPublic {
  id: string;
  full_name: string;
  avatar_url: string | null;
  role: UserRole;
}

export interface ClassroomMember {
  user: UserPublic;
  role: MemberRole;
  joined_at: string;
}

export interface ClassroomPeople {
  teachers: ClassroomMember[];
  students: ClassroomMember[];
}

export interface Announcement {
  id: string;
  classroom_id: string;
  author_id: string | null;
  author: UserPublic | null;
  content: string;
  created_at: string;
  updated_at: string;
}

export type CommentTarget = "assignment" | "announcement";

/** (Named `CommentRecord` so it does not shadow the DOM `Comment` type.) */
export interface CommentRecord {
  id: string;
  author_id: string | null;
  author: UserPublic | null;
  target_type: CommentTarget;
  target_id: string;
  body: string;
  created_at: string;
}

export interface AttachmentRef {
  file_id: string;
  name: string;
  mime_type: string | null;
}

export type AssignmentState = "draft" | "published";

export interface Assignment {
  id: string;
  classroom_id: string;
  title: string;
  description: string | null;
  due_at: string | null;
  max_points: number;
  attachments: AttachmentRef[];
  state: AssignmentState;
  created_at: string;
  updated_at: string;
}

export interface AssignmentCreateInput {
  title: string;
  description?: string;
  due_at?: string;
  max_points?: number;
  state?: AssignmentState;
}

export type SubmissionState = "assigned" | "turned_in" | "graded" | "returned";

export interface Submission {
  id: string;
  assignment_id: string;
  student_id: string;
  student: UserPublic | null;
  content: string | null;
  attachments: AttachmentRef[];
  state: SubmissionState;
  grade: number | null;
  feedback: string | null;
  submitted_at: string | null;
  graded_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface SubmissionList extends Page<Submission> {
  not_submitted_count: number;
}

export interface QuizSummary {
  id: string;
  classroom_id: string;
  title: string;
  description: string | null;
  time_limit_minutes: number | null;
  due_at: string | null;
  published: boolean;
  allow_retake: boolean;
  created_at: string;
  updated_at: string;
}

export interface QuizCreateInput {
  title: string;
  description?: string;
  time_limit_minutes?: number;
  allow_retake?: boolean;
  published?: boolean;
}

export interface AttemptResult {
  id: string;
  quiz_id: string;
  student_id: string;
  started_at: string;
  submitted_at: string | null;
  expires_at: string | null;
  score: number | null;
  max_score: number | null;
  pending_manual_grading: boolean;
}

export interface MyAttempt {
  attempt: AttemptResult | null;
  attempts_used: number;
  can_start: boolean;
}

export interface QuizResults {
  quiz_id: string;
  attempt_count: number;
  submitted_count: number;
  not_attempted_count: number;
  average_score: number | null;
  max_score: number;
}

export interface Material {
  id: string;
  classroom_id: string;
  title: string;
  description: string | null;
  attachments: AttachmentRef[];
  created_at: string;
  updated_at: string;
}

export interface MaterialCreateInput {
  title: string;
  description?: string;
}
ts
const dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });

/** "Oct 11, 2026, 3:30 PM" in the user's locale and time zone. */
export function formatDateTime(iso: string): string {
  return dateTime.format(new Date(iso));
}

/** `datetime-local` input value -> UTC ISO string (the API needs timezone-aware datetimes). */
export function toIsoFromLocalInput(value: string): string | undefined {
  if (!value) return undefined;
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? undefined : date.toISOString();
}

/** 45 -> "45", 8.5 -> "8.50". */
export function formatPoints(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(2);
}
ts
import { useCallback, useEffect, useRef, useState } from "react";

/** Copies text; `copied` is true for `resetMs` afterwards. Works on plain http via a fallback. */
export function useCopyToClipboard(resetMs = 2000) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const copy = useCallback(
    async (text: string): Promise<boolean> => {
      try {
        if (navigator.clipboard && window.isSecureContext) {
          await navigator.clipboard.writeText(text);
        } else {
          const area = document.createElement("textarea");
          area.value = text;
          area.setAttribute("readonly", "");
          area.style.position = "fixed";
          area.style.opacity = "0";
          document.body.appendChild(area);
          area.select();
          const ok = document.execCommand("copy");
          document.body.removeChild(area);
          if (!ok) return false;
        }
      } catch {
        return false;
      }
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), resetMs);
      return true;
    },
    [resetMs],
  );

  return { copied, copy };
}
UI building blocks
tsx
import * as SheetPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const Sheet = SheetPrimitive.Root;
const SheetTrigger = SheetPrimitive.Trigger;
const SheetClose = SheetPrimitive.Close;

const SheetContent = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <SheetPrimitive.Portal>
    <SheetPrimitive.Overlay className="fixed inset-0 z-50 bg-black/60 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0" />
    <SheetPrimitive.Content
      ref={ref}
      className={cn(
        "fixed inset-y-0 right-0 z-50 flex h-full w-full max-w-md flex-col gap-4 border-l bg-background p-6 shadow-lg duration-300 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:slide-in-from-right",
        className,
      )}
      {...props}
    >
      {children}
      <SheetPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2">
        <X className="h-4 w-4" aria-hidden="true" />
        <span className="sr-only">Close</span>
      </SheetPrimitive.Close>
    </SheetPrimitive.Content>
  </SheetPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";

const SheetHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 pr-6 text-left", className)} {...props} />
);

const SheetTitle = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Title>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Title ref={ref} className={cn("text-lg font-semibold", className)} {...props} />
));
SheetTitle.displayName = "SheetTitle";

const SheetDescription = React.forwardRef<
  React.ElementRef<typeof SheetPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof SheetPrimitive.Description>
>(({ className, ...props }, ref) => (
  <SheetPrimitive.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
));
SheetDescription.displayName = "SheetDescription";

export { Sheet, SheetClose, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger };
tsx
import * as React from "react";

import { cn } from "@/lib/utils";

const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea
      ref={ref}
      className={cn(
        "flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    />
  ),
);
Textarea.displayName = "Textarea";

export { Textarea };
tsx
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";

import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold",
  {
    variants: {
      variant: {
        default: "border-transparent bg-primary text-primary-foreground",
        secondary: "border-transparent bg-secondary text-secondary-foreground",
        destructive: "border-transparent bg-destructive/10 text-destructive",
        outline: "text-foreground",
      },
    },
    defaultVariants: { variant: "secondary" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant }), className)} {...props} />;
}
tsx
import * as React from "react";

import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface TextAreaFieldProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  id: string;
  label: string;
  error?: string | null;
  hint?: string;
}

/** Label + textarea + hint + error, wired together with `aria-describedby`. */
export const TextAreaField = React.forwardRef<HTMLTextAreaElement, TextAreaFieldProps>(
  ({ id, label, error, hint, className, ...props }, ref) => {
    const describedBy =
      [hint ? `${id}-hint` : null, error ? `${id}-error` : null].filter(Boolean).join(" ") || undefined;
    return (
      <div className="space-y-2">
        <Label htmlFor={id}>
          {label}
          {props.required ? (
            <span aria-hidden="true" className="text-destructive">
              {" "}
              *
            </span>
          ) : null}
        </Label>
        <Textarea
          id={id}
          ref={ref}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          className={cn(error && "border-destructive", className)}
          {...props}
        />
        {hint ? (
          <p id={`${id}-hint`} className="text-xs text-muted-foreground">
            {hint}
          </p>
        ) : null}
        {error ? (
          <p id={`${id}-error`} className="text-sm text-destructive">
            {error}
          </p>
        ) : null}
      </div>
    );
  },
);
TextAreaField.displayName = "TextAreaField";
tsx
import type { ReactNode } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";

interface AsyncListProps {
  isPending: boolean;
  error: unknown;
  onRetry: () => void;
  isEmpty: boolean;
  emptyText: string;
  loadingLabel?: string;
  children: ReactNode;
}

/** Loading, error (with retry) and empty states in one place; renders `children` otherwise. */
export function AsyncList({
  isPending,
  error,
  onRetry,
  isEmpty,
  emptyText,
  loadingLabel = "Loading…",
  children,
}: AsyncListProps) {
  if (isPending) return <Spinner label={loadingLabel} />;
  if (error) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={onRetry}>
          Try again
        </Button>
      </div>
    );
  }
  if (isEmpty) {
    return (
      <p className="rounded-lg border border-dashed p-6 text-center text-sm text-muted-foreground">{emptyText}</p>
    );
  }
  return <>{children}</>;
}
tsx
import { useCallback, useState, type ReactNode } from "react";

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

/**
 * Open/close state for a form dialog. A dialog cannot be closed while its request is in
 * flight, and `onReset` clears the form every time it opens or closes.
 */
export function useFormDialog({ isPending, onReset }: { isPending: boolean; onReset: () => void }) {
  const [open, setOpen] = useState(false);

  const onOpenChange = useCallback(
    (next: boolean) => {
      if (isPending) return;
      onReset();
      setOpen(next);
    },
    [isPending, onReset],
  );
  const close = useCallback(() => {
    onReset();
    setOpen(false);
  }, [onReset]);

  return { open, onOpenChange, close };
}

interface FormDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: ReactNode;
  title: string;
  description: string;
  submitLabel: string;
  pendingLabel: string;
  isPending: boolean;
  /** The mutation error, if any. */
  error: unknown;
  /** Validate and send. Called on submit (native validation is off; we show our own messages). */
  onSubmit: () => void;
  children: ReactNode;
}

export function FormDialog({
  open,
  onOpenChange,
  trigger,
  title,
  description,
  submitLabel,
  pendingLabel,
  isPending,
  error,
  onSubmit,
  children,
}: FormDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogTrigger asChild>{trigger}</DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        <form
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            onSubmit();
          }}
          className="space-y-4"
        >
          <ErrorAlert message={error ? getErrorMessage(error) : null} />
          {children}
          <DialogFooter>
            <Button type="button" variant="outline" disabled={isPending} onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={isPending}>
              {isPending ? pendingLabel : submitLabel}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
Layout: header, tabs, layout
tsx
import { ArrowLeft, Check, Copy } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import type { Classroom } from "@/types";

export function ClassroomHeader({ classroom }: { classroom: Classroom }) {
  const { copied, copy } = useCopyToClipboard();
  const [copyFailed, setCopyFailed] = useState(false);

  const details = [classroom.section, classroom.subject, classroom.room ? `Room ${classroom.room}` : null]
    .filter(Boolean)
    .join(" · ");

  async function onCopy(code: string) {
    setCopyFailed(!(await copy(code)));
  }

  return (
    <header className="space-y-3">
      <Link
        to="/classes"
        className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All classes
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <h1 className="break-words text-2xl font-semibold tracking-tight">{classroom.name}</h1>
          {details ? <p className="text-muted-foreground">{details}</p> : null}
          <div className="mt-2 flex flex-wrap gap-2">
            <Badge className="capitalize">{classroom.my_role}</Badge>
            {classroom.is_archived ? <Badge variant="destructive">Archived</Badge> : null}
          </div>
        </div>

        {classroom.join_code ? (
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Join code (share with your students)</p>
            <div className="mt-1 flex items-center gap-3">
              <code className="text-xl font-semibold tracking-widest">{classroom.join_code}</code>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void onCopy(classroom.join_code as string)}
              >
                {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                {copied ? "Copied" : "Copy"}
                <span className="sr-only"> join code</span>
              </Button>
            </div>
            <p role="status" className="mt-1 min-h-4 text-xs text-muted-foreground">
              {copied ? "Join code copied to the clipboard." : copyFailed ? "Could not copy. Select the code and copy it manually." : ""}
            </p>
          </div>
        ) : null}
      </div>

      {classroom.is_archived ? (
        <p role="note" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          This class is archived and read-only. Unarchive it to post, grade or change anything.
        </p>
      ) : null}
    </header>
  );
}
tsx
import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { suffix: "", label: "Stream", end: true },
  { suffix: "/classwork", label: "Classwork", end: false },
  { suffix: "/people", label: "People", end: false },
  { suffix: "/grades", label: "Grades", end: false },
];

/** Link-based tabs: each tab is a real route, so back/forward and deep links work. */
export function ClassroomTabs({ classroomId }: { classroomId: string }) {
  const base = `/classes/${classroomId}`;
  return (
    <nav aria-label="Classroom sections" className="border-b">
      <ul className="-mb-px flex gap-1 overflow-x-auto">
        {TABS.map(({ suffix, label, end }) => (
          <li key={label}>
            <NavLink
              to={`${base}${suffix}`}
              end={end}
              className={({ isActive }) =>
                cn(
                  "block whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
tsx
import { Link, Outlet, useParams } from "react-router-dom";

import { getStatus } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { ClassroomHeader } from "@/features/classrooms/components/ClassroomHeader";
import { ClassroomTabs } from "@/features/classrooms/components/ClassroomTabs";
import { useClassroom } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Header + tabs for every /classes/:classroomId/* page. Loads the classroom once. */
export function ClassroomLayout() {
  const { classroomId = "" } = useParams();
  const { data: classroom, isPending, error } = useClassroom(classroomId);
  useDocumentTitle(classroom?.name);

  if (isPending) return <Spinner label="Loading class…" />;

  if (error || !classroom) {
    const missing = getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="py-10 text-center">
        <h1 className="text-xl font-semibold">{missing ? "Class not found" : "Could not load this class"}</h1>
        <p className="mt-1 text-muted-foreground">
          {missing ? "It does not exist, or you are not a member." : "Please try again in a moment."}
        </p>
        <Link to="/classes" className="mt-4 inline-block text-primary underline-offset-4 hover:underline">
          Back to your classes
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <ClassroomHeader classroom={classroom} />
      <ClassroomTabs classroomId={classroom.id} />
      <Outlet context={{ classroom }} />
    </div>
  );
}
Classrooms feature (people)
ts
import { api } from "@/api/client";
import type { Classroom, ClassroomCreateInput, ClassroomPeople } from "@/types";

export const classroomsApi = {
  list: (params?: { include_archived?: boolean; limit?: number; offset?: number }) =>
    api.get<Classroom[]>("/classrooms", { params }).then((r) => r.data),

  get: (id: string) => api.get<Classroom>(`/classrooms/${id}`).then((r) => r.data),

  /** Teachers/admins only (the API answers 403 otherwise). */
  create: (body: ClassroomCreateInput) =>
    api.post<Classroom>("/classrooms", body).then((r) => r.data),

  /** Joins as a student. 404 = unknown code, 409 = already a member, 403 = archived. */
  join: (joinCode: string) =>
    api.post<Classroom>("/classrooms/join", { join_code: joinCode }).then((r) => r.data),

  people: (id: string) => api.get<ClassroomPeople>(`/classrooms/${id}/people`).then((r) => r.data),
};
ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { classroomsApi } from "@/features/classrooms/api";
import type { Classroom } from "@/types";

const root = ["classrooms"] as const;

export const classroomKeys = {
  all: root,
  /** Prefix of every list query (archived or not): use it to invalidate. */
  lists: () => [...root, "list"] as const,
  list: (includeArchived: boolean) => [...root, "list", { includeArchived }] as const,
  detail: (id: string) => [...root, "detail", id] as const,
  people: (id: string) => [...root, "people", id] as const,
};

export function useClassrooms(options: { includeArchived?: boolean } = {}) {
  const includeArchived = options.includeArchived ?? false;
  return useQuery({
    queryKey: classroomKeys.list(includeArchived),
    // 100 is the API maximum; pagination UI comes later.
    queryFn: () => classroomsApi.list({ include_archived: includeArchived, limit: 100 }),
  });
}

export function useClassroom(id: string) {
  return useQuery({
    queryKey: classroomKeys.detail(id),
    queryFn: () => classroomsApi.get(id),
    enabled: Boolean(id),
  });
}

export function useClassroomPeople(id: string) {
  return useQuery({
    queryKey: classroomKeys.people(id),
    queryFn: () => classroomsApi.people(id),
    enabled: Boolean(id),
  });
}

/** Shared by create and join: seed the detail cache (instant navigation), refresh the lists. */
function useRegisterNewClassroom() {
  const queryClient = useQueryClient();
  return (classroom: Classroom) => {
    queryClient.setQueryData(classroomKeys.detail(classroom.id), classroom);
    void queryClient.invalidateQueries({ queryKey: classroomKeys.lists() });
  };
}

export function useCreateClassroom() {
  const register = useRegisterNewClassroom();
  return useMutation({
    mutationFn: classroomsApi.create,
    onSuccess: register,
  });
}

export function useJoinClassroom() {
  const register = useRegisterNewClassroom();
  return useMutation({
    mutationFn: classroomsApi.join,
    onSuccess: register,
  });
}
tsx
import { useAuthStore } from "@/store/auth";
import type { ClassroomMember } from "@/types";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function PeopleList({ title, members }: { title: string; members: ClassroomMember[] }) {
  const myId = useAuthStore((s) => s.user?.id);
  return (
    <section aria-labelledby={`people-${title}`}>
      <h2 id={`people-${title}`} className="border-b pb-2 text-lg font-semibold">
        {title} <span className="text-sm font-normal text-muted-foreground">({members.length})</span>
      </h2>
      {members.length === 0 ? (
        <p className="py-4 text-sm text-muted-foreground">Nobody here yet.</p>
      ) : (
        <ul className="divide-y">
          {members.map((member) => (
            <li key={member.user.id} className="flex items-center gap-3 py-3">
              <span
                aria-hidden="true"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
              >
                {initials(member.user.full_name)}
              </span>
              <span className="min-w-0 break-words font-medium">
                {member.user.full_name}
                {member.user.id === myId ? <span className="font-normal text-muted-foreground"> (you)</span> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
Announcements and comments
ts
import { api } from "@/api/client";
import type { Announcement, Page } from "@/types";

export const announcementsApi = {
  list: (classroomId: string, params: { limit: number; offset: number }) =>
    api.get<Page<Announcement>>(`/classrooms/${classroomId}/announcements`, { params }).then((r) => r.data),

  /** Classroom teachers only. */
  create: (classroomId: string, content: string) =>
    api.post<Announcement>(`/classrooms/${classroomId}/announcements`, { content }).then((r) => r.data),

  /** Classroom teachers only; the announcement's comments are deleted with it. */
  remove: (classroomId: string, id: string) =>
    api.delete(`/classrooms/${classroomId}/announcements/${id}`).then(() => undefined),
};
ts
import { useInfiniteQuery, useMutation, useQueryClient } from "@tanstack/react-query";

import { announcementsApi } from "@/features/announcements/api";

const PAGE_SIZE = 20;

export const announcementKeys = {
  list: (classroomId: string) => ["announcements", "list", classroomId] as const,
};

/** Newest first; `fetchNextPage` loads the next 20. */
export function useAnnouncements(classroomId: string) {
  return useInfiniteQuery({
    queryKey: announcementKeys.list(classroomId),
    initialPageParam: 0,
    queryFn: ({ pageParam }) => announcementsApi.list(classroomId, { limit: PAGE_SIZE, offset: pageParam }),
    getNextPageParam: (last) => {
      const next = last.offset + last.items.length;
      return last.items.length > 0 && next < last.total ? next : undefined;
    },
  });
}

export function useCreateAnnouncement(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (content: string) => announcementsApi.create(classroomId, content),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: announcementKeys.list(classroomId) }),
  });
}

export function useDeleteAnnouncement(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => announcementsApi.remove(classroomId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: announcementKeys.list(classroomId) }),
  });
}
ts
import { api } from "@/api/client";
import type { CommentRecord, CommentTarget, Page } from "@/types";

export const commentsApi = {
  list: (targetType: CommentTarget, targetId: string) =>
    api
      .get<Page<CommentRecord>>("/comments", {
        params: { target_type: targetType, target_id: targetId, limit: 100 },
      })
      .then((r) => r.data),

  create: (targetType: CommentTarget, targetId: string, body: string) =>
    api
      .post<CommentRecord>("/comments", { target_type: targetType, target_id: targetId, body })
      .then((r) => r.data),

  /** The author, or a classroom teacher. */
  remove: (id: string) => api.delete(`/comments/${id}`).then(() => undefined),
};
ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { commentsApi } from "@/features/comments/api";
import type { CommentTarget } from "@/types";

export const commentKeys = {
  list: (targetType: CommentTarget, targetId: string) => ["comments", targetType, targetId] as const,
};

export function useComments(targetType: CommentTarget, targetId: string) {
  return useQuery({
    queryKey: commentKeys.list(targetType, targetId),
    queryFn: () => commentsApi.list(targetType, targetId),
  });
}

export function useCreateComment(targetType: CommentTarget, targetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: string) => commentsApi.create(targetType, targetId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: commentKeys.list(targetType, targetId) }),
  });
}

export function useDeleteComment(targetType: CommentTarget, targetId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (commentId: string) => commentsApi.remove(commentId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: commentKeys.list(targetType, targetId) }),
  });
}
tsx
import { useState, type FormEvent } from "react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useCreateAnnouncement } from "@/features/announcements/hooks";

/** Teacher-only form at the top of the stream. */
export function AnnouncementComposer({ classroomId }: { classroomId: string }) {
  const create = useCreateAnnouncement(classroomId);
  const [content, setContent] = useState("");
  const [fieldError, setFieldError] = useState<string | null>(null);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = content.trim();
    if (!text) {
      setFieldError("Write something to announce.");
      document.getElementById("announcement-content")?.focus();
      return;
    }
    setFieldError(null);
    create.mutate(text, { onSuccess: () => setContent("") });
  }

  return (
    <Card>
      <CardContent className="p-4">
        <form onSubmit={onSubmit} noValidate className="space-y-3">
          <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />
          <TextAreaField
            id="announcement-content"
            label="Announce something to your class"
            rows={3}
            maxLength={10_000}
            value={content}
            onChange={(e) => {
              setContent(e.target.value);
              setFieldError(null);
            }}
            error={fieldError}
          />
          <div className="flex justify-end">
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Posting…" : "Post"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
tsx
import { MessageSquare, Trash2 } from "lucide-react";
import { useState, type FormEvent } from "react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useComments, useCreateComment, useDeleteComment } from "@/features/comments/hooks";
import { formatDateTime } from "@/lib/format";
import { useAuthStore } from "@/store/auth";
import type { Announcement, Classroom } from "@/types";

function CommentsPanel({ announcement, classroom }: { announcement: Announcement; classroom: Classroom }) {
  const me = useAuthStore((s) => s.user);
  const comments = useComments("announcement", announcement.id);
  const create = useCreateComment("announcement", announcement.id);
  const remove = useDeleteComment("announcement", announcement.id);
  const [body, setBody] = useState("");

  const canModerate = classroom.my_role === "teacher";
  const readOnly = classroom.is_archived;
  const items = comments.data?.items ?? [];

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const text = body.trim();
    if (!text) return;
    create.mutate(text, { onSuccess: () => setBody("") });
  }

  return (
    <>
      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        <AsyncList
          isPending={comments.isPending}
          error={comments.error}
          onRetry={() => void comments.refetch()}
          isEmpty={items.length === 0}
          emptyText="No comments yet. Start the conversation."
          loadingLabel="Loading comments…"
        >
          <ul aria-label="Comments" className="space-y-4">
            {items.map((comment) => {
              const canDelete = !readOnly && (comment.author_id === me?.id || canModerate);
              const deleting = remove.isPending && remove.variables === comment.id;
              return (
                <li key={comment.id} className="rounded-md border p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium">{comment.author?.full_name ?? "Deleted user"}</p>
                    {canDelete ? (
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="-mr-2 -mt-1 h-7 px-2"
                        disabled={deleting}
                        onClick={() => remove.mutate(comment.id)}
                      >
                        <Trash2 aria-hidden="true" />
                        <span className="sr-only">Delete comment by {comment.author?.full_name ?? "deleted user"}</span>
                      </Button>
                    ) : null}
                  </div>
                  <time dateTime={comment.created_at} className="text-xs text-muted-foreground">
                    {formatDateTime(comment.created_at)}
                  </time>
                  <p className="mt-1 whitespace-pre-wrap break-words text-sm">{comment.body}</p>
                </li>
              );
            })}
          </ul>
          {comments.data && comments.data.total > items.length ? (
            <p className="mt-3 text-xs text-muted-foreground">Showing the first {items.length} comments.</p>
          ) : null}
        </AsyncList>
        <ErrorAlert className="mt-3" message={remove.isError ? getErrorMessage(remove.error) : null} />
      </div>

      {readOnly ? (
        <p className="text-sm text-muted-foreground">This class is archived, so new comments are disabled.</p>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-2 border-t pt-4">
          <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />
          <TextAreaField
            id={`comment-${announcement.id}`}
            label="Add a comment"
            rows={3}
            maxLength={5_000}
            value={body}
            onChange={(e) => setBody(e.target.value)}
          />
          <div className="flex justify-end">
            <Button type="submit" size="sm" disabled={create.isPending || !body.trim()}>
              {create.isPending ? "Posting…" : "Comment"}
            </Button>
          </div>
        </form>
      )}
    </>
  );
}

/** "Comments" button that opens a right-side drawer; comments load only when it opens. */
export function CommentsDrawer({ announcement, classroom }: { announcement: Announcement; classroom: Classroom }) {
  return (
    <Sheet>
      <SheetTrigger asChild>
        <Button variant="ghost" size="sm">
          <MessageSquare aria-hidden="true" />
          Comments
        </Button>
      </SheetTrigger>
      <SheetContent>
        <SheetHeader>
          <SheetTitle>Comments</SheetTitle>
          <SheetDescription className="line-clamp-3">{announcement.content}</SheetDescription>
        </SheetHeader>
        <CommentsPanel announcement={announcement} classroom={classroom} />
      </SheetContent>
    </Sheet>
  );
}
tsx
import { Trash2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CommentsDrawer } from "@/features/announcements/components/CommentsDrawer";
import { useDeleteAnnouncement } from "@/features/announcements/hooks";
import { formatDateTime } from "@/lib/format";
import type { Announcement, Classroom } from "@/types";

export function AnnouncementItem({ announcement, classroom }: { announcement: Announcement; classroom: Classroom }) {
  const remove = useDeleteAnnouncement(classroom.id);
  const canDelete = classroom.my_role === "teacher" && !classroom.is_archived;

  function onDelete() {
    if (window.confirm("Delete this announcement and all of its comments?")) {
      remove.mutate(announcement.id);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-2">
          <div>
            <p className="font-medium">{announcement.author?.full_name ?? "Deleted user"}</p>
            <time dateTime={announcement.created_at} className="text-xs text-muted-foreground">
              {formatDateTime(announcement.created_at)}
            </time>
          </div>
          {canDelete ? (
            <Button type="button" variant="ghost" size="sm" disabled={remove.isPending} onClick={onDelete}>
              <Trash2 aria-hidden="true" />
              <span className="sr-only">Delete announcement</span>
            </Button>
          ) : null}
        </div>

        <p className="whitespace-pre-wrap break-words">{announcement.content}</p>
        <ErrorAlert message={remove.isError ? getErrorMessage(remove.error) : null} />

        <div className="border-t pt-2">
          <CommentsDrawer announcement={announcement} classroom={classroom} />
        </div>
      </CardContent>
    </Card>
  );
}
Assignments
ts
import { api } from "@/api/client";
import type { Assignment, AssignmentCreateInput, AssignmentState, Page, Submission, SubmissionList } from "@/types";

export const assignmentsApi = {
  /** Students only receive published assignments. */
  list: (classroomId: string) =>
    api
      .get<Page<Assignment>>(`/classrooms/${classroomId}/assignments`, { params: { limit: 100 } })
      .then((r) => r.data),

  create: (classroomId: string, body: AssignmentCreateInput) =>
    api.post<Assignment>(`/classrooms/${classroomId}/assignments`, body).then((r) => r.data),

  update: (id: string, body: { state?: AssignmentState }) =>
    api.patch<Assignment>(`/assignments/${id}`, body).then((r) => r.data),

  /** Students: your own submission, or `null` when you have not turned anything in. */
  mySubmission: (id: string) =>
    api.get<Submission | null>(`/assignments/${id}/my-submission`).then((r) => r.data),

  /** Teachers: first 100 submissions plus `not_submitted_count`. */
  submissions: (id: string) =>
    api.get<SubmissionList>(`/assignments/${id}/submissions`, { params: { limit: 100 } }).then((r) => r.data),
};
ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { assignmentsApi } from "@/features/assignments/api";
import type { AssignmentCreateInput, AssignmentState } from "@/types";

export const assignmentKeys = {
  list: (classroomId: string) => ["assignments", "list", classroomId] as const,
  mySubmission: (id: string) => ["assignments", "my-submission", id] as const,
  submissions: (id: string) => ["assignments", "submissions", id] as const,
};

export function useAssignments(classroomId: string) {
  return useQuery({
    queryKey: assignmentKeys.list(classroomId),
    queryFn: () => assignmentsApi.list(classroomId),
  });
}

export function useCreateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: AssignmentCreateInput) => assignmentsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}

export function useUpdateAssignment(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, state }: { id: string; state: AssignmentState }) => assignmentsApi.update(id, { state }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: assignmentKeys.list(classroomId) }),
  });
}
tsx
import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog, useFormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateAssignment } from "@/features/assignments/hooks";
import { toIsoFromLocalInput } from "@/lib/format";
import type { AssignmentCreateInput } from "@/types";

const EMPTY = { title: "", description: "", due: "", points: "100", publish: false };
type FormState = typeof EMPTY;
type Errors = { title?: string; points?: string; due?: string };

export function CreateAssignmentDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateAssignment(classroomId);
  const { reset: resetMutation } = create;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});

  const resetAll = useCallback(() => {
    setForm(EMPTY);
    setErrors({});
    resetMutation();
  }, [resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit() {
    const title = form.title.trim();
    const points = Number(form.points);
    const dueAt = toIsoFromLocalInput(form.due);

    const next: Errors = {};
    if (!title) next.title = "Title is required.";
    if (!Number.isInteger(points) || points < 1 || points > 100_000) {
      next.points = "Enter a whole number from 1 to 100000.";
    }
    if (form.due && !dueAt) next.due = "Enter a valid date and time.";
    setErrors(next);

    const firstInvalid = next.title ? "assignment-title" : next.points ? "assignment-points" : next.due ? "assignment-due" : null;
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus();
      return;
    }

    const body: AssignmentCreateInput = {
      title,
      max_points: points,
      state: form.publish ? "published" : "draft",
    };
    const description = form.description.trim();
    if (description) body.description = description;
    if (dueAt) body.due_at = dueAt;
    create.mutate(body, { onSuccess: dialog.close });
  }

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
      onSubmit={onSubmit}
    >
      <TextField
        id="assignment-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={errors.title}
      />
      <TextAreaField
        id="assignment-description"
        label="Instructions"
        rows={4}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          id="assignment-due"
          label="Due date"
          type="datetime-local"
          value={form.due}
          onChange={bind("due")}
          error={errors.due}
        />
        <TextField
          id="assignment-points"
          label="Points"
          type="number"
          inputMode="numeric"
          min={1}
          max={100_000}
          step={1}
          value={form.points}
          onChange={bind("points")}
          error={errors.points}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={form.publish}
          onChange={(e) => setForm((current) => ({ ...current, publish: e.target.checked }))}
        />
        Publish now
      </label>
    </FormDialog>
  );
}
tsx
import { Paperclip } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CreateAssignmentDialog } from "@/features/assignments/components/CreateAssignmentDialog";
import { useAssignments, useUpdateAssignment } from "@/features/assignments/hooks";
import { formatDateTime } from "@/lib/format";
import type { Assignment, Classroom } from "@/types";

function AssignmentItem({ assignment, classroom }: { assignment: Assignment; classroom: Classroom }) {
  const update = useUpdateAssignment(classroom.id);
  const canPublish = classroom.my_role === "teacher" && !classroom.is_archived && assignment.state === "draft";

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{assignment.title}</h3>
            <p className="text-sm text-muted-foreground">
              {assignment.due_at ? (
                <>
                  Due <time dateTime={assignment.due_at}>{formatDateTime(assignment.due_at)}</time>
                </>
              ) : (
                "No due date"
              )}
              {" · "}
              {assignment.max_points} points
            </p>
          </div>
          <div className="flex items-center gap-2">
            {assignment.state === "draft" ? <Badge variant="outline">Draft</Badge> : null}
            {canPublish ? (
              <Button
                type="button"
                size="sm"
                disabled={update.isPending}
                onClick={() => update.mutate({ id: assignment.id, state: "published" })}
              >
                {update.isPending ? "Publishing…" : "Publish"}
              </Button>
            ) : null}
          </div>
        </div>

        {assignment.description ? (
          <p className="line-clamp-2 whitespace-pre-wrap break-words text-sm">{assignment.description}</p>
        ) : null}
        {assignment.attachments.length > 0 ? (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Paperclip className="h-3 w-3" aria-hidden="true" />
            {assignment.attachments.length} attachment{assignment.attachments.length === 1 ? "" : "s"}
          </p>
        ) : null}
        <ErrorAlert message={update.isError ? getErrorMessage(update.error) : null} />
      </CardContent>
    </Card>
  );
}

export function AssignmentsSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useAssignments(classroom.id);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="assignments-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="assignments-title" className="text-xl font-semibold">
          Assignments
        </h2>
        {canCreate ? <CreateAssignmentDialog classroomId={classroom.id} /> : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No assignments yet."
        loadingLabel="Loading assignments…"
      >
        <ul className="space-y-3">
          {data?.items.map((assignment) => (
            <li key={assignment.id}>
              <AssignmentItem assignment={assignment} classroom={classroom} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
Quizzes
ts
import { api } from "@/api/client";
import type { MyAttempt, Page, QuizCreateInput, QuizResults, QuizSummary } from "@/types";

export const quizzesApi = {
  /** Students only receive published quizzes. */
  list: (classroomId: string) =>
    api.get<Page<QuizSummary>>(`/classrooms/${classroomId}/quizzes`, { params: { limit: 100 } }).then((r) => r.data),

  create: (classroomId: string, body: QuizCreateInput) =>
    api.post<unknown>(`/classrooms/${classroomId}/quizzes`, body).then((r) => r.data),

  /** Students: latest attempt, attempts used, and whether they can (re)start. */
  myAttempt: (id: string) => api.get<MyAttempt>(`/quizzes/${id}/my-attempt`).then((r) => r.data),

  /** Teachers: statistics (we only need the counters, so ask for one attempt). */
  results: (id: string) => api.get<QuizResults>(`/quizzes/${id}/results`, { params: { limit: 1 } }).then((r) => r.data),
};
ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { quizzesApi } from "@/features/quizzes/api";
import type { QuizCreateInput } from "@/types";

export const quizKeys = {
  list: (classroomId: string) => ["quizzes", "list", classroomId] as const,
  myAttempt: (id: string) => ["quizzes", "my-attempt", id] as const,
  results: (id: string) => ["quizzes", "results", id] as const,
};

export function useQuizzes(classroomId: string) {
  return useQuery({
    queryKey: quizKeys.list(classroomId),
    queryFn: () => quizzesApi.list(classroomId),
  });
}

export function useCreateQuiz(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: QuizCreateInput) => quizzesApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: quizKeys.list(classroomId) }),
  });
}
tsx
import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog, useFormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateQuiz } from "@/features/quizzes/hooks";
import type { QuizCreateInput } from "@/types";

const EMPTY = { title: "", description: "", minutes: "", retake: false };
type FormState = typeof EMPTY;
type Errors = { title?: string; minutes?: string };

/** Creates a DRAFT quiz. The question editor arrives with the quiz pages. */
export function CreateQuizDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateQuiz(classroomId);
  const { reset: resetMutation } = create;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});

  const resetAll = useCallback(() => {
    setForm(EMPTY);
    setErrors({});
    resetMutation();
  }, [resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit() {
    const title = form.title.trim();
    const minutesText = form.minutes.trim();
    const minutes = Number(minutesText);

    const next: Errors = {};
    if (!title) next.title = "Title is required.";
    if (minutesText && (!Number.isInteger(minutes) || minutes < 1 || minutes > 600)) {
      next.minutes = "Enter a whole number of minutes from 1 to 600, or leave it empty.";
    }
    setErrors(next);
    const firstInvalid = next.title ? "quiz-title" : next.minutes ? "quiz-minutes" : null;
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus();
      return;
    }

    const body: QuizCreateInput = { title, published: false, allow_retake: form.retake };
    const description = form.description.trim();
    if (description) body.description = description;
    if (minutesText) body.time_limit_minutes = minutes;
    create.mutate(body, { onSuccess: dialog.close });
  }

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Create quiz
        </Button>
      }
      title="Create a quiz"
      description="The quiz is saved as a draft. Adding questions and publishing it comes with the quiz editor."
      submitLabel="Create draft"
      pendingLabel="Creating…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={onSubmit}
    >
      <TextField
        id="quiz-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={errors.title}
      />
      <TextAreaField
        id="quiz-description"
        label="Description"
        rows={3}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
      <TextField
        id="quiz-minutes"
        label="Time limit (minutes)"
        type="number"
        inputMode="numeric"
        min={1}
        max={600}
        step={1}
        hint="Leave empty for no time limit."
        value={form.minutes}
        onChange={bind("minutes")}
        error={errors.minutes}
      />
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={form.retake}
          onChange={(e) => setForm((current) => ({ ...current, retake: e.target.checked }))}
        />
        Allow students to retake the quiz
      </label>
    </FormDialog>
  );
}
tsx
import { AsyncList } from "@/components/common/AsyncList";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { CreateQuizDialog } from "@/features/quizzes/components/CreateQuizDialog";
import { useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, QuizSummary } from "@/types";

function QuizItem({ quiz, isTeacher }: { quiz: QuizSummary; isTeacher: boolean }) {
  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex flex-wrap items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{quiz.title}</h3>
            <p className="text-sm text-muted-foreground">
              {quiz.due_at ? (
                <>
                  Due <time dateTime={quiz.due_at}>{formatDateTime(quiz.due_at)}</time>
                </>
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
        {isTeacher && !quiz.published ? (
          <p className="text-xs text-muted-foreground">Draft: add questions before publishing (quiz editor comes next).</p>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function QuizzesSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useQuizzes(classroom.id);
  const isTeacher = classroom.my_role === "teacher";
  const canCreate = isTeacher && !classroom.is_archived;

  return (
    <section aria-labelledby="quizzes-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="quizzes-title" className="text-xl font-semibold">
          Quizzes
        </h2>
        {canCreate ? <CreateQuizDialog classroomId={classroom.id} /> : null}
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
              <QuizItem quiz={quiz} isTeacher={isTeacher} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
Materials
ts
import { api } from "@/api/client";
import type { Material, MaterialCreateInput, Page } from "@/types";

export const materialsApi = {
  list: (classroomId: string) =>
    api.get<Page<Material>>(`/classrooms/${classroomId}/materials`, { params: { limit: 100 } }).then((r) => r.data),

  /** Classroom teachers only; every student gets a notification. */
  create: (classroomId: string, body: MaterialCreateInput) =>
    api.post<Material>(`/classrooms/${classroomId}/materials`, body).then((r) => r.data),

  remove: (classroomId: string, id: string) =>
    api.delete(`/classrooms/${classroomId}/materials/${id}`).then(() => undefined),
};
ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { materialsApi } from "@/features/materials/api";
import type { MaterialCreateInput } from "@/types";

export const materialKeys = {
  list: (classroomId: string) => ["materials", "list", classroomId] as const,
};

export function useMaterials(classroomId: string) {
  return useQuery({
    queryKey: materialKeys.list(classroomId),
    queryFn: () => materialsApi.list(classroomId),
  });
}

export function useCreateMaterial(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MaterialCreateInput) => materialsApi.create(classroomId, body),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: materialKeys.list(classroomId) }),
  });
}

export function useDeleteMaterial(classroomId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => materialsApi.remove(classroomId, id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: materialKeys.list(classroomId) }),
  });
}
tsx
import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog, useFormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateMaterial } from "@/features/materials/hooks";
import type { MaterialCreateInput } from "@/types";

const EMPTY = { title: "", description: "" };
type FormState = typeof EMPTY;

export function CreateMaterialDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateMaterial(classroomId);
  const { reset: resetMutation } = create;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [titleError, setTitleError] = useState<string | null>(null);

  const resetAll = useCallback(() => {
    setForm(EMPTY);
    setTitleError(null);
    resetMutation();
  }, [resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit() {
    const title = form.title.trim();
    if (!title) {
      setTitleError("Title is required.");
      document.getElementById("material-title")?.focus();
      return;
    }
    setTitleError(null);
    const body: MaterialCreateInput = { title };
    const description = form.description.trim();
    if (description) body.description = description;
    create.mutate(body, { onSuccess: dialog.close });
  }

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Add material
        </Button>
      }
      title="Add a material"
      description="Students are notified. File attachments come with the file picker step."
      submitLabel="Post"
      pendingLabel="Posting…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={onSubmit}
    >
      <TextField
        id="material-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={titleError}
      />
      <TextAreaField
        id="material-description"
        label="Description"
        rows={4}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
    </FormDialog>
  );
}
tsx
import { Paperclip, Trash2 } from "lucide-react";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CreateMaterialDialog } from "@/features/materials/components/CreateMaterialDialog";
import { useDeleteMaterial, useMaterials } from "@/features/materials/hooks";
import { formatDateTime } from "@/lib/format";
import type { Classroom, Material } from "@/types";

function MaterialItem({ material, classroom }: { material: Material; classroom: Classroom }) {
  const remove = useDeleteMaterial(classroom.id);
  const canDelete = classroom.my_role === "teacher" && !classroom.is_archived;

  function onDelete() {
    if (window.confirm(`Delete “${material.title}”?`)) remove.mutate(material.id);
  }

  return (
    <Card>
      <CardContent className="space-y-2 p-4">
        <div className="flex items-start justify-between gap-2">
          <div className="min-w-0">
            <h3 className="break-words font-medium">{material.title}</h3>
            <p className="text-sm text-muted-foreground">
              Posted <time dateTime={material.created_at}>{formatDateTime(material.created_at)}</time>
            </p>
          </div>
          {canDelete ? (
            <Button type="button" variant="ghost" size="sm" disabled={remove.isPending} onClick={onDelete}>
              <Trash2 aria-hidden="true" />
              <span className="sr-only">Delete {material.title}</span>
            </Button>
          ) : null}
        </div>
        {material.description ? (
          <p className="line-clamp-3 whitespace-pre-wrap break-words text-sm">{material.description}</p>
        ) : null}
        {material.attachments.length > 0 ? (
          <p className="flex items-center gap-1 text-xs text-muted-foreground">
            <Paperclip className="h-3 w-3" aria-hidden="true" />
            {material.attachments.length} attachment{material.attachments.length === 1 ? "" : "s"}
          </p>
        ) : null}
        <ErrorAlert message={remove.isError ? getErrorMessage(remove.error) : null} />
      </CardContent>
    </Card>
  );
}

export function MaterialsSection({ classroom }: { classroom: Classroom }) {
  const { data, isPending, error, refetch } = useMaterials(classroom.id);
  const canCreate = classroom.my_role === "teacher" && !classroom.is_archived;

  return (
    <section aria-labelledby="materials-title" className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 id="materials-title" className="text-xl font-semibold">
          Materials
        </h2>
        {canCreate ? <CreateMaterialDialog classroomId={classroom.id} /> : null}
      </div>
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="No materials yet."
        loadingLabel="Loading materials…"
      >
        <ul className="space-y-3">
          {data?.items.map((material) => (
            <li key={material.id}>
              <MaterialItem material={material} classroom={classroom} />
            </li>
          ))}
        </ul>
      </AsyncList>
    </section>
  );
}
Grades
tsx
import { useQueries } from "@tanstack/react-query";

import { AsyncList } from "@/components/common/AsyncList";
import { assignmentsApi } from "@/features/assignments/api";
import { assignmentKeys, useAssignments } from "@/features/assignments/hooks";
import { quizzesApi } from "@/features/quizzes/api";
import { quizKeys, useQuizzes } from "@/features/quizzes/hooks";
import { formatDateTime, formatPoints } from "@/lib/format";

interface Row {
  key: string;
  kind: "Assignment" | "Quiz";
  title: string;
  due: string | null;
  status: string;
  score: string;
}

/** A student's own status and score for every published assignment and quiz. */
export function StudentGrades({ classroomId }: { classroomId: string }) {
  const assignments = useAssignments(classroomId);
  const quizzes = useQuizzes(classroomId);
  const assignmentItems = assignments.data?.items ?? [];
  const quizItems = quizzes.data?.items ?? [];

  const submissions = useQueries({
    queries: assignmentItems.map((a) => ({
      queryKey: assignmentKeys.mySubmission(a.id),
      queryFn: () => assignmentsApi.mySubmission(a.id),
    })),
  });
  const attempts = useQueries({
    queries: quizItems.map((q) => ({
      queryKey: quizKeys.myAttempt(q.id),
      queryFn: () => quizzesApi.myAttempt(q.id),
    })),
  });

  const now = new Date();
  const rows: Row[] = [
    ...assignmentItems.map((a, i): Row => {
      const result = submissions[i];
      const submission = result?.data;
      let status = "…";
      let score = "—";
      if (result?.isError) status = "Unavailable";
      else if (result && !result.isPending) {
        if (!submission) status = a.due_at && new Date(a.due_at) < now ? "Missing" : "Not turned in";
        else if (submission.state === "returned") {
          status = "Returned";
          if (submission.grade !== null) score = `${formatPoints(submission.grade)} / ${a.max_points}`;
        } else status = "Turned in"; // graded work stays hidden until the teacher returns it
      }
      return { key: `a-${a.id}`, kind: "Assignment", title: a.title, due: a.due_at, status, score };
    }),
    ...quizItems.map((q, i): Row => {
      const result = attempts[i];
      const attempt = result?.data?.attempt;
      let status = "…";
      let score = "—";
      if (result?.isError) status = "Unavailable";
      else if (result && !result.isPending) {
        if (!attempt) status = "Not started";
        else if (!attempt.submitted_at) status = "In progress";
        else {
          status = attempt.pending_manual_grading ? "Awaiting grading" : "Submitted";
          if (attempt.score !== null && attempt.max_score !== null) {
            score = `${formatPoints(attempt.score)} / ${formatPoints(attempt.max_score)}`;
          }
        }
      }
      return { key: `q-${q.id}`, kind: "Quiz", title: q.title, due: q.due_at, status, score };
    }),
  ];

  const isPending = assignments.isPending || quizzes.isPending;
  const error = assignments.error ?? quizzes.error;

  return (
    <AsyncList
      isPending={isPending}
      error={error}
      onRetry={() => {
        void assignments.refetch();
        void quizzes.refetch();
      }}
      isEmpty={rows.length === 0}
      emptyText="Nothing to grade yet. Published assignments and quizzes will appear here."
      loadingLabel="Loading your grades…"
    >
      <div className="overflow-x-auto rounded-lg border">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">Your work and scores in this class</caption>
          <thead className="bg-muted/50 text-muted-foreground">
            <tr>
              <th scope="col" className="px-4 py-2 font-medium">Work</th>
              <th scope="col" className="px-4 py-2 font-medium">Type</th>
              <th scope="col" className="px-4 py-2 font-medium">Due</th>
              <th scope="col" className="px-4 py-2 font-medium">Status</th>
              <th scope="col" className="px-4 py-2 text-right font-medium">Score</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {rows.map((row) => (
              <tr key={row.key}>
                <th scope="row" className="px-4 py-3 font-medium">{row.title}</th>
                <td className="px-4 py-3">{row.kind}</td>
                <td className="whitespace-nowrap px-4 py-3">{row.due ? formatDateTime(row.due) : "—"}</td>
                <td className="px-4 py-3">{row.status}</td>
                <td className="whitespace-nowrap px-4 py-3 text-right">{row.score}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AsyncList>
  );
}
tsx
import { useQueries } from "@tanstack/react-query";

import { AsyncList } from "@/components/common/AsyncList";
import { assignmentsApi } from "@/features/assignments/api";
import { assignmentKeys, useAssignments } from "@/features/assignments/hooks";
import { quizzesApi } from "@/features/quizzes/api";
import { quizKeys, useQuizzes } from "@/features/quizzes/hooks";
import { formatPoints } from "@/lib/format";

const TH = "px-4 py-2 font-medium";

/** Class-wide progress per published assignment and quiz. */
export function TeacherGrades({ classroomId }: { classroomId: string }) {
  const assignments = useAssignments(classroomId);
  const quizzes = useQuizzes(classroomId);
  const published = (assignments.data?.items ?? []).filter((a) => a.state === "published");
  const publishedQuizzes = (quizzes.data?.items ?? []).filter((q) => q.published);

  const submissions = useQueries({
    queries: published.map((a) => ({
      queryKey: assignmentKeys.submissions(a.id),
      queryFn: () => assignmentsApi.submissions(a.id),
    })),
  });
  const results = useQueries({
    queries: publishedQuizzes.map((q) => ({
      queryKey: quizKeys.results(q.id),
      queryFn: () => quizzesApi.results(q.id),
    })),
  });

  return (
    <div className="space-y-8">
      <section aria-labelledby="grades-assignments">
        <h2 id="grades-assignments" className="mb-3 text-xl font-semibold">Assignments</h2>
        <AsyncList
          isPending={assignments.isPending}
          error={assignments.error}
          onRetry={() => void assignments.refetch()}
          isEmpty={published.length === 0}
          emptyText="No published assignments yet."
        >
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Submission progress per assignment</caption>
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th scope="col" className={TH}>Assignment</th>
                  <th scope="col" className={`${TH} text-right`}>Points</th>
                  <th scope="col" className={`${TH} text-right`}>Turned in</th>
                  <th scope="col" className={`${TH} text-right`}>To grade</th>
                  <th scope="col" className={`${TH} text-right`}>Graded / returned</th>
                  <th scope="col" className={`${TH} text-right`}>Not submitted</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {published.map((assignment, i) => {
                  const result = submissions[i];
                  const data = result?.data;
                  const cell = (value: number | undefined) =>
                    result?.isError ? "!" : data ? String(value ?? 0) : "…";
                  return (
                    <tr key={assignment.id}>
                      <th scope="row" className="px-4 py-3 font-medium">{assignment.title}</th>
                      <td className="px-4 py-3 text-right">{assignment.max_points}</td>
                      <td className="px-4 py-3 text-right">{cell(data?.total)}</td>
                      <td className="px-4 py-3 text-right">
                        {cell(data?.items.filter((s) => s.state === "turned_in").length)}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {cell(data?.items.filter((s) => s.state === "graded" || s.state === "returned").length)}
                      </td>
                      <td className="px-4 py-3 text-right">{cell(data?.not_submitted_count)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncList>
      </section>

      <section aria-labelledby="grades-quizzes">
        <h2 id="grades-quizzes" className="mb-3 text-xl font-semibold">Quizzes</h2>
        <AsyncList
          isPending={quizzes.isPending}
          error={quizzes.error}
          onRetry={() => void quizzes.refetch()}
          isEmpty={publishedQuizzes.length === 0}
          emptyText="No published quizzes yet."
        >
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-left text-sm">
              <caption className="sr-only">Results per quiz</caption>
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th scope="col" className={TH}>Quiz</th>
                  <th scope="col" className={`${TH} text-right`}>Submitted</th>
                  <th scope="col" className={`${TH} text-right`}>Not attempted</th>
                  <th scope="col" className={`${TH} text-right`}>Average (best attempts)</th>
                </tr>
              </thead>
              <tbody className="divide-y">
                {publishedQuizzes.map((quiz, i) => {
                  const result = results[i];
                  const data = result?.data;
                  const placeholder = result?.isError ? "!" : "…";
                  return (
                    <tr key={quiz.id}>
                      <th scope="row" className="px-4 py-3 font-medium">{quiz.title}</th>
                      <td className="px-4 py-3 text-right">{data ? data.submitted_count : placeholder}</td>
                      <td className="px-4 py-3 text-right">{data ? data.not_attempted_count : placeholder}</td>
                      <td className="px-4 py-3 text-right">
                        {data
                          ? data.average_score === null
                            ? "—"
                            : `${formatPoints(data.average_score)} / ${formatPoints(data.max_score)}`
                          : placeholder}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </AsyncList>
      </section>

      <p className="text-xs text-muted-foreground">
        Counts cover the first 100 submissions of each assignment. A per-student gradebook comes with the grading screens.
      </p>
    </div>
  );
}
Pages and router
tsx
import { Button } from "@/components/ui/button";
import { AsyncList } from "@/components/common/AsyncList";
import { AnnouncementComposer } from "@/features/announcements/components/AnnouncementComposer";
import { AnnouncementItem } from "@/features/announcements/components/AnnouncementItem";
import { useAnnouncements } from "@/features/announcements/hooks";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function StreamPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Stream`);

  const canPost = classroom.my_role === "teacher" && !classroom.is_archived;
  const query = useAnnouncements(classroom.id);
  const items = query.data?.pages.flatMap((page) => page.items) ?? [];

  return (
    <section aria-labelledby="stream-title" className="mx-auto max-w-3xl space-y-4">
      <h2 id="stream-title" className="sr-only">
        Announcements
      </h2>

      {canPost ? <AnnouncementComposer classroomId={classroom.id} /> : null}

      <AsyncList
        isPending={query.isPending}
        error={query.error}
        onRetry={() => void query.refetch()}
        isEmpty={items.length === 0}
        emptyText={
          classroom.my_role === "teacher"
            ? "No announcements yet. Post the first one above."
            : "No announcements yet."
        }
        loadingLabel="Loading announcements…"
      >
        <ul className="space-y-4">
          {items.map((announcement) => (
            <li key={announcement.id}>
              <AnnouncementItem announcement={announcement} classroom={classroom} />
            </li>
          ))}
        </ul>
        {query.hasNextPage ? (
          <div className="flex justify-center pt-2">
            <Button
              variant="outline"
              disabled={query.isFetchingNextPage}
              onClick={() => void query.fetchNextPage()}
            >
              {query.isFetchingNextPage ? "Loading…" : "Load more"}
            </Button>
          </div>
        ) : null}
      </AsyncList>
    </section>
  );
}
tsx
import { useClassroomContext } from "@/features/classrooms/context";
import { AssignmentsSection } from "@/features/assignments/components/AssignmentsSection";
import { MaterialsSection } from "@/features/materials/components/MaterialsSection";
import { QuizzesSection } from "@/features/quizzes/components/QuizzesSection";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassworkPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Classwork`);

  return (
    <div className="space-y-10">
      <AssignmentsSection classroom={classroom} />
      <QuizzesSection classroom={classroom} />
      <MaterialsSection classroom={classroom} />
    </div>
  );
}
tsx
import { AsyncList } from "@/components/common/AsyncList";
import { useClassroomContext } from "@/features/classrooms/context";
import { PeopleList } from "@/features/classrooms/components/PeopleList";
import { useClassroomPeople } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PeoplePage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · People`);
  const { data, isPending, error, refetch } = useClassroomPeople(classroom.id);

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={false}
        emptyText=""
        loadingLabel="Loading people…"
      >
        <PeopleList title="Teachers" members={data?.teachers ?? []} />
        <PeopleList title="Students" members={data?.students ?? []} />
      </AsyncList>
    </div>
  );
}
tsx
import { useClassroomContext } from "@/features/classrooms/context";
import { StudentGrades } from "@/features/grades/components/StudentGrades";
import { TeacherGrades } from "@/features/grades/components/TeacherGrades";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function GradesPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Grades`);

  return classroom.my_role === "teacher" ? (
    <TeacherGrades classroomId={classroom.id} />
  ) : (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold">Your grades</h2>
      <p className="text-sm text-muted-foreground">Scores for assignments appear after your teacher returns your work.</p>
      <StudentGrades classroomId={classroom.id} />
    </div>
  );
}
tsx
import { createBrowserRouter, Navigate, useParams } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
import { GradesPage } from "@/pages/classroom/GradesPage";
import { PeoplePage } from "@/pages/classroom/PeoplePage";
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

/** `/classrooms/:id/...` is an alias of `/classes/:id/...`. */
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
              // later: classwork/assignments/:id, classwork/quizzes/:id, materials/:id
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
1. Start
bash
# backend (from repo root)
docker compose up -d postgres redis
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm run build        # must type-check cleanly
npm run dev          # http://localhost:5173
No new packages and no backend changes.
2. Manual test checklist
Use two browser profiles: teacher Tina and student Sam. Sam joins Tina’s class with the join code.
#	Do this	Expected
1	As Tina, open her class	Header with name, details, “teacher” badge and the join code with a Copy button. Tabs: Stream, Classwork, People, Grades
2	Click Copy, paste somewhere	The code is pasted. A “Join code copied” status is announced next to the button
3	As Sam, open the same class	Same header with no join code; no composer on Stream, no create buttons on Classwork
4	Visit /classrooms/<id>/people	Redirects to /classes/<id>/people
5	Stream, as Tina: submit an empty announcement	“Write something to announce.” and focus moves to the field. Nothing is sent
6	Post “Welcome!”	It appears at the top, and Sam sees it after a refresh
7	Post 25 announcements	Only 20 show, with Load more at the bottom. It loads the rest
8	As Sam, click Comments on an announcement	A drawer slides in from the right. Post “Thanks!” and it appears. Esc closes the drawer
9	As Tina, open the same drawer	She sees Sam’s comment with a delete button, and can delete it. As Sam, you see delete only on your own comments
10	As Tina, delete an announcement (confirm dialog)	It disappears, and its comments are gone
11	Classwork, as Tina: Create assignment with a blank title	“Title is required.” Points 0 shows “Enter a whole number…”
12	Create a draft assignment, due date set	Card shows “Draft” and a Publish button. Sam does not see it
13	Click Publish	Badge disappears. Sam sees it on refresh, and it shows up in his To-Do data
14	Create quiz with a 20-minute limit and retakes	A card with “Draft”, “20 min” and “Retakes allowed”. Sam does not see it. Time limit 0 or 1000 shows an inline error
15	Add material	Card appears. Sam gets a notification (GET /notifications shows material_posted)
16	As Tina, delete a material	Confirm dialog, then it disappears
17	People tab	Teachers and Students lists with counts; your own row says “(you)”; no emails shown
18	Grades as Sam	A table of published work: “Not turned in” (or “Missing” when overdue), score “—”
19	Submit work for Sam in Swagger (POST /assignments/{id}/submit), then reload Grades	Status “Turned in”
20	In Swagger, grade it (PATCH /submissions/{id}/grade)	Sam still sees “Turned in” with no score
21	Return it (PATCH /submissions/{id}/return)	Sam sees “Returned” and the score, e.g. 45 / 50
22	Grades as Tina	Assignment table with turned-in, to-grade, graded and not-submitted counts; quiz table with stats
23	Archive the class (PATCH /classrooms/{id} {"is_archived": true}) and reload	Red “archived and read-only” banner. Composer, create buttons, Publish and delete buttons are gone. The comment form says comments are disabled. Reading still works
24	Stop the API and open Classwork	Each section shows its own error with Try again; other sections are unaffected
25	Press Tab through a dialog or the drawer	Focus stays inside it, and returns to the trigger on close
3. Expected API traffic
Page	Requests
Any classroom tab	GET /classrooms/{id} once (cached across tabs)
Stream	GET /classrooms/{id}/announcements?limit=20&offset=0; “Load more” uses offset=20
Comments drawer (on open only)	GET /comments?target_type=announcement&target_id=…&limit=100
Classwork	GET …/assignments, …/quizzes, …/materials (all limit=100)
People	GET /classrooms/{id}/people
Grades (student)	the assignment and quiz lists, then one GET /assignments/{id}/my-submission and one GET /quizzes/{id}/my-attempt per item
Grades (teacher)	the lists, then GET /assignments/{id}/submissions?limit=100 and GET /quizzes/{id}/results?limit=1 per published item
Troubleshooting
Problem	Fix
Cannot find module '@/features/...'	A file was not created at the exact path in the tree. Re-run the touch block and check the spelling
The drawer appears but does not slide	tailwindcss-animate must be in plugins in tailwind.config.ts (STEP 13 has it)
403 creating something as a teacher	The classroom is archived, or you are a student there. The create buttons are hidden in both cases, so check you are on the right account
Student sees “Unavailable” in a grades row	That one request failed (for example a rate limit). Reload the tab
Due date saved an hour off	datetime-local is interpreted in your browser’s time zone and sent as UTC. The display converts back, so the card shows the time you entered
Copy button does nothing on a LAN IP over http	Browsers block the Clipboard API on non-secure origins. The fallback handles most cases. If it still fails, the status line tells you to copy manually
New assignment does not show for the student	It is a draft. Click Publish
Nothing opens when clicking an assignment or quiz	Expected for now. Detail pages (submit, grade, take quiz) are the next frontend steps
ClassroomSidebar import error	Delete components/layout/ClassroomSidebar.tsx. Nothing imports it any more
Reply NEXT for STEP 16.

```