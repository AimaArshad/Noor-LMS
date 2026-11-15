```ts  
STEP 14: Auth pages and classroom wiring
What STEP 13 already covers. Three of your bullets were built in STEP 13, so I’m not rewriting them:
src/api/auth.ts already has register, login, refresh and me. It is unchanged.
Tokens live in memory (the Zustand store) and are mirrored to localStorage. If storage is blocked, the in-memory session still works until reload.
Refresh-on-401 is in src/api/client.ts. Concurrent 401s share one refresh, because the backend rotates refresh tokens.
What this step adds:
Classroom API, hooks and dialogs: create, join, list.
Pages with your file names: Login.tsx, Register.tsx, Home.tsx.
Register has a teacher/student role picker.
A new dialog.tsx, which needs one new dependency, @radix-ui/react-dialog.
Design decisions:
Create vs join buttons. “Create class” shows only for teachers and admins, matching the API. “Join class” shows for everyone. Joining always makes you a student, even for teachers (STEP 6 rule).
After create or join the new classroom is put into the query cache and you are taken to /classes/:id. Lists refetch in the background.
Dialogs can’t be closed while a request is in flight. Closing resets their form and error state.
Register then sign in. If registration works but the automatic sign-in fails (a rate limit, say), you land on /login with a notice instead of an error that suggests the account wasn’t created.
Join code input is upper-cased as you type, with spaces and dashes stripped. The backend accepts 4-16 letters or digits.
Classes list requests limit=100, the API maximum. Pagination UI comes later.
Files in this step
text
frontend/
├── package.json                                  ← EDIT    (+ @radix-ui/react-dialog)
└── src/
    ├── types/index.ts                            ← EDIT    (+ ClassroomCreateInput)
    ├── routes/index.tsx                          ← REPLACE (new page imports)
    ├── components/
    │   ├── ui/dialog.tsx                         ← NEW
    │   └── common/
    │       ├── TextField.tsx                     ← NEW
    │       └── ErrorAlert.tsx                    ← NEW
    ├── features/classrooms/
    │   ├── api.ts                                ← REPLACE (+ create, join)
    │   ├── hooks.ts                              ← REPLACE (+ useCreateClassroom, useJoinClassroom)
    │   └── components/
    │       ├── ClassroomCard.tsx                 ← NEW
    │       ├── ClassroomsOverview.tsx            ← NEW
    │       ├── ClassroomActions.tsx              ← NEW
    │       ├── CreateClassroomDialog.tsx         ← NEW
    │       └── JoinClassroomDialog.tsx           ← NEW
    └── pages/
        ├── Login.tsx                             ← NEW  (replaces pages/auth/LoginPage.tsx)
        ├── Register.tsx                          ← NEW  (replaces pages/auth/RegisterPage.tsx)
        ├── Home.tsx                              ← NEW  (replaces pages/HomePage.tsx)
        └── ClassesPage.tsx                       ← REPLACE
bash
cd frontend
npm install @radix-ui/react-dialog

mkdir -p src/features/classrooms/components
touch src/components/ui/dialog.tsx \
      src/components/common/{TextField,ErrorAlert}.tsx \
      src/features/classrooms/components/{ClassroomCard,ClassroomsOverview,ClassroomActions,CreateClassroomDialog,JoinClassroomDialog}.tsx \
      src/pages/{Login,Register,Home}.tsx

# the old pages are replaced by the new ones
rm src/pages/auth/LoginPage.tsx src/pages/auth/RegisterPage.tsx src/pages/HomePage.tsx
rmdir src/pages/auth
Edits
json
    "@radix-ui/react-dialog": "^1.1.2",
ts
export interface ClassroomCreateInput {
  name: string;
  section?: string;
  subject?: string;
  room?: string;
}
UI building blocks
tsx
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";

import { cn } from "@/lib/utils";

const Dialog = DialogPrimitive.Root;
const DialogTrigger = DialogPrimitive.Trigger;
const DialogPortal = DialogPrimitive.Portal;
const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      "fixed inset-0 z-50 bg-black/60 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0",
      className,
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed left-1/2 top-1/2 z-50 grid max-h-[90vh] w-[calc(100%-2rem)] max-w-lg -translate-x-1/2 -translate-y-1/2 gap-4 overflow-y-auto rounded-lg border bg-background p-6 shadow-lg duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0 data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95",
        className,
      )}
      {...props}
    >
      {children}
      <DialogPrimitive.Close className="absolute right-4 top-4 rounded-sm opacity-70 transition-opacity hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:pointer-events-none">
        <X className="h-4 w-4" aria-hidden="true" />
        <span className="sr-only">Close</span>
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPortal>
));
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col space-y-1.5 text-left", className)} {...props} />
);
DialogHeader.displayName = "DialogHeader";

const DialogFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex flex-col-reverse gap-2 sm:flex-row sm:justify-end", className)} {...props} />
);
DialogFooter.displayName = "DialogFooter";

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn("text-lg font-semibold leading-none tracking-tight", className)}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description ref={ref} className={cn("text-sm text-muted-foreground", className)} {...props} />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
};
tsx
import * as React from "react";

import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";

interface TextFieldProps extends React.InputHTMLAttributes<HTMLInputElement> {
  id: string;
  label: string;
  /** Validation message; also sets `aria-invalid`. */
  error?: string | null;
  hint?: string;
}

/** Label + input + hint + error, wired together with `aria-describedby`. */
export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
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
        <Input
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
TextField.displayName = "TextField";
tsx
import { cn } from "@/lib/utils";

/** A form- or page-level error. `role="alert"` makes screen readers announce it at once. */
export function ErrorAlert({ message, className }: { message: string | null | undefined; className?: string }) {
  if (!message) return null;
  return (
    <p
      role="alert"
      className={cn(
        "rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive",
        className,
      )}
    >
      {message}
    </p>
  );
}
Classrooms feature
ts
import { api } from "@/api/client";
import type { Classroom, ClassroomCreateInput } from "@/types";

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
import { Link } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Classroom } from "@/types";

export function ClassroomCard({ classroom }: { classroom: Classroom }) {
  const details = [classroom.section, classroom.subject].filter(Boolean).join(" · ");
  return (
    <Link
      to={`/classes/${classroom.id}`}
      className="block h-full rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-colors hover:bg-accent/50">
        <CardHeader>
          <CardTitle className="text-lg">{classroom.name}</CardTitle>
          <CardDescription>{details || "No details"}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-secondary px-2 py-0.5 font-medium capitalize">{classroom.my_role}</span>
          {classroom.is_archived ? (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 font-medium text-destructive">Archived</span>
          ) : null}
          {classroom.join_code ? (
            <span className="ml-auto text-muted-foreground">
              Code <code className="font-semibold tracking-widest text-foreground">{classroom.join_code}</code>
            </span>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}
tsx
import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";
import { ClassroomCard } from "@/features/classrooms/components/ClassroomCard";
import { useClassrooms } from "@/features/classrooms/hooks";
import { useAuthStore } from "@/store/auth";

/** The grid of the user's classrooms, with loading, error and empty states. */
export function ClassroomsOverview({ includeArchived = false }: { includeArchived?: boolean }) {
  const role = useAuthStore((s) => s.user?.role);
  const { data, isPending, isError, error, refetch, isFetching } = useClassrooms({ includeArchived });

  if (isPending) return <Spinner label="Loading your classes…" />;

  if (isError) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
          Try again
        </Button>
      </div>
    );
  }

  if (data.length === 0) {
    const canCreate = role === "teacher" || role === "admin";
    return (
      <div className="rounded-lg border border-dashed p-10 text-center">
        <p className="font-medium">You are not in any class yet.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {canCreate
            ? "Create your first class, or join one with a code."
            : "Ask your teacher for a join code, then use “Join class”."}
        </p>
      </div>
    );
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {data.map((classroom) => (
        <li key={classroom.id}>
          <ClassroomCard classroom={classroom} />
        </li>
      ))}
    </ul>
  );
}
tsx
import { CreateClassroomDialog } from "@/features/classrooms/components/CreateClassroomDialog";
import { JoinClassroomDialog } from "@/features/classrooms/components/JoinClassroomDialog";
import { useAuthStore } from "@/store/auth";

/** "Join class" for everyone, "Create class" for teachers and admins. */
export function ClassroomActions() {
  const role = useAuthStore((s) => s.user?.role);
  const canCreate = role === "teacher" || role === "admin";
  return (
    <div className="flex flex-wrap gap-2">
      <JoinClassroomDialog />
      {canCreate ? <CreateClassroomDialog /> : null}
    </div>
  );
}
tsx
import { Plus } from "lucide-react";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextField } from "@/components/common/TextField";
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
import { useCreateClassroom } from "@/features/classrooms/hooks";
import type { ClassroomCreateInput } from "@/types";

const EMPTY = { name: "", section: "", subject: "", room: "" };
type FormState = typeof EMPTY;

export function CreateClassroomDialog() {
  const navigate = useNavigate();
  const create = useCreateClassroom();
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [nameError, setNameError] = useState<string | null>(null);

  function handleOpenChange(next: boolean) {
    if (create.isPending) return; // never abandon an in-flight request
    create.reset();
    setForm(EMPTY);
    setNameError(null);
    setOpen(next);
  }

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const name = form.name.trim();
    if (!name) {
      setNameError("Class name is required.");
      document.getElementById("class-name")?.focus();
      return;
    }
    setNameError(null);

    const body: ClassroomCreateInput = { name };
    for (const key of ["section", "subject", "room"] as const) {
      const value = form[key].trim();
      if (value) body[key] = value;
    }
    create.mutate(body, {
      onSuccess: (classroom) => {
        setOpen(false);
        setForm(EMPTY);
        navigate(`/classes/${classroom.id}`);
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <Plus aria-hidden="true" />
          Create class
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a class</DialogTitle>
          <DialogDescription>
            You will get a join code to share with your students.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />
          <TextField
            id="class-name"
            label="Class name"
            required
            maxLength={200}
            autoComplete="off"
            value={form.name}
            onChange={bind("name")}
            error={nameError}
          />
          <div className="grid gap-4 sm:grid-cols-2">
            <TextField id="class-section" label="Section" maxLength={100} value={form.section} onChange={bind("section")} />
            <TextField id="class-subject" label="Subject" maxLength={100} value={form.subject} onChange={bind("subject")} />
          </div>
          <TextField id="class-room" label="Room" maxLength={100} value={form.room} onChange={bind("room")} />

          <DialogFooter>
            <Button type="button" variant="outline" disabled={create.isPending} onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={create.isPending}>
              {create.isPending ? "Creating…" : "Create class"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
tsx
import { LogIn } from "lucide-react";
import { useState, type ChangeEvent, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextField } from "@/components/common/TextField";
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
import { useJoinClassroom } from "@/features/classrooms/hooks";

// Same rule as the backend (ClassroomJoin): 4-16 letters or digits.
const CODE_PATTERN = /^[A-Z0-9]{4,16}$/;

export function JoinClassroomDialog() {
  const navigate = useNavigate();
  const join = useJoinClassroom();
  const [open, setOpen] = useState(false);
  const [code, setCode] = useState("");
  const [codeError, setCodeError] = useState<string | null>(null);

  function handleOpenChange(next: boolean) {
    if (join.isPending) return;
    join.reset();
    setCode("");
    setCodeError(null);
    setOpen(next);
  }

  // Upper-case as the user types and drop spaces / dashes (codes are easy to mistype).
  function onCodeChange(event: ChangeEvent<HTMLInputElement>) {
    setCode(event.target.value.toUpperCase().replace(/[^A-Z0-9]/g, ""));
    setCodeError(null);
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!CODE_PATTERN.test(code)) {
      setCodeError("Enter the 4-16 letter or digit code from your teacher.");
      document.getElementById("join-code")?.focus();
      return;
    }
    join.mutate(code, {
      onSuccess: (classroom) => {
        setOpen(false);
        setCode("");
        navigate(`/classes/${classroom.id}`);
      },
    });
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <LogIn aria-hidden="true" />
          Join class
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Join a class</DialogTitle>
          <DialogDescription>Ask your teacher for the class join code.</DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <ErrorAlert message={join.isError ? getErrorMessage(join.error) : null} />
          <TextField
            id="join-code"
            label="Join code"
            required
            maxLength={16}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            className="font-mono uppercase tracking-widest"
            value={code}
            onChange={onCodeChange}
            error={codeError}
          />
          <DialogFooter>
            <Button type="button" variant="outline" disabled={join.isPending} onClick={() => handleOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" disabled={join.isPending}>
              {join.isPending ? "Joining…" : "Join class"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
Pages
tsx
import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextField } from "@/components/common/TextField";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function LoginPage() {
  useDocumentTitle("Sign in");
  const login = useAuthStore((s) => s.login);
  const location = useLocation();
  // Set by the register page when the account was created but the automatic sign-in failed.
  const notice = (location.state as { notice?: string } | null)?.notice;

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      // GuestRoute redirects (to the page you came from, or Home) once the store has a user.
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      description="Use your EduConnect account."
      footer={
        <>
          No account?{" "}
          <Link to="/register" className="text-primary underline-offset-4 hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        {notice ? (
          <p role="status" className="rounded-md border bg-secondary p-3 text-sm">
            {notice}
          </p>
        ) : null}
        <ErrorAlert message={error} />
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          autoFocus
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
tsx
import { GraduationCap, School, type LucideIcon } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { authApi } from "@/api/auth";
import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextField } from "@/components/common/TextField";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/button";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";
import type { RegisterInput } from "@/types";

type Role = RegisterInput["role"];

const ROLE_OPTIONS: { value: Role; label: string; description: string; icon: LucideIcon }[] = [
  { value: "student", label: "Student", description: "Join classes with a code.", icon: GraduationCap },
  { value: "teacher", label: "Teacher", description: "Create classes and post work.", icon: School },
];

interface FieldErrors {
  full_name?: string;
  password?: string;
}

/** Mirrors the backend rules: 8-72 bytes, at least one letter and one digit. */
function passwordProblem(password: string): string | undefined {
  if (new TextEncoder().encode(password).length > 72) return "Password must be at most 72 bytes.";
  if (password.length < 8) return "Password must be at least 8 characters.";
  if (!/[A-Za-z]/.test(password) || !/\d/.test(password)) {
    return "Password must contain at least one letter and one digit.";
  }
  return undefined;
}

export function RegisterPage() {
  useDocumentTitle("Create account");
  const navigate = useNavigate();
  const login = useAuthStore((s) => s.login);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const problems: FieldErrors = {};
    if (!fullName.trim()) problems.full_name = "Enter your full name.";
    const pwProblem = passwordProblem(password);
    if (pwProblem) problems.password = pwProblem;
    setFieldErrors(problems);
    if (problems.full_name || problems.password) {
      document.getElementById(problems.full_name ? "full_name" : "password")?.focus();
      return;
    }

    const credentials = { email: email.trim(), password };
    setSubmitting(true);
    try {
      await authApi.register({ ...credentials, full_name: fullName.trim(), role });
    } catch (err) {
      setError(getErrorMessage(err));
      setSubmitting(false);
      return;
    }

    try {
      await login(credentials); // GuestRoute then redirects to Home
    } catch {
      // The account exists; only the automatic sign-in failed (e.g. rate limit).
      navigate("/login", { replace: true, state: { notice: "Account created. Please sign in." } });
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Create your account"
      description="Teachers create classes; students join them with a code."
      footer={
        <>
          Already registered?{" "}
          <Link to="/login" className="text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <ErrorAlert message={error} />

        <fieldset className="space-y-2">
          <legend className="text-sm font-medium">I am a</legend>
          <div className="grid grid-cols-2 gap-3">
            {ROLE_OPTIONS.map(({ value, label, description, icon: Icon }) => (
              <label
                key={value}
                className={cn(
                  "flex cursor-pointer flex-col gap-1 rounded-lg border p-3 text-sm transition-colors hover:bg-accent/50 focus-within:ring-2 focus-within:ring-ring",
                  role === value && "border-primary bg-primary/5",
                )}
              >
                <span className="flex items-center gap-2 font-medium">
                  <input
                    type="radio"
                    name="role"
                    value={value}
                    checked={role === value}
                    onChange={() => setRole(value)}
                    className="h-4 w-4 accent-primary"
                  />
                  <Icon className="h-4 w-4" aria-hidden="true" />
                  {label}
                </span>
                <span className="text-xs text-muted-foreground">{description}</span>
              </label>
            ))}
          </div>
        </fieldset>

        <TextField
          id="full_name"
          label="Full name"
          autoComplete="name"
          required
          maxLength={255}
          value={fullName}
          onChange={(e) => setFullName(e.target.value)}
          error={fieldErrors.full_name}
        />
        <TextField
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <TextField
          id="password"
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          hint="8-72 characters, with at least one letter and one digit."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={fieldErrors.password}
        />
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Creating account…" : "Create account"}
        </Button>
      </form>
    </AuthShell>
  );
}
tsx
import { ClassroomActions } from "@/features/classrooms/components/ClassroomActions";
import { ClassroomsOverview } from "@/features/classrooms/components/ClassroomsOverview";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function HomePage() {
  useDocumentTitle("Home");
  const user = useAuthStore((s) => s.user);

  return (
    <section aria-labelledby="page-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
            Welcome{user ? `, ${user.full_name}` : ""}
          </h1>
          <p className="mt-1 text-muted-foreground">Pick a class, or join or create one.</p>
        </div>
        <ClassroomActions />
      </div>

      <h2 className="mb-4 mt-8 text-lg font-semibold">Your classes</h2>
      <ClassroomsOverview />
    </section>
  );
}
tsx
import { useState } from "react";

import { ClassroomActions } from "@/features/classrooms/components/ClassroomActions";
import { ClassroomsOverview } from "@/features/classrooms/components/ClassroomsOverview";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassesPage() {
  useDocumentTitle("Classes");
  const [includeArchived, setIncludeArchived] = useState(false);

  return (
    <section aria-labelledby="page-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
          Classes
        </h1>
        <ClassroomActions />
      </div>

      <label className="mb-4 mt-4 flex w-fit items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
          className="h-4 w-4 accent-primary"
        />
        Show archived classes
      </label>

      <ClassroomsOverview includeArchived={includeArchived} />
    </section>
  );
}
Router
tsx
import { createBrowserRouter } from "react-router-dom";

import { AppLayout } from "@/components/layout/AppLayout";
import { ClassroomLayout } from "@/components/layout/ClassroomLayout";
import { AdminPage } from "@/pages/AdminPage";
import { ClassworkPage } from "@/pages/classroom/ClassworkPage";
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
            ],
          },
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

# frontend (second terminal)
cd frontend
npm install                 # picks up @radix-ui/react-dialog
npm run build               # must finish with no type errors
npm run dev                 # http://localhost:5173
2. Manual test checklist
Use two browsers, or one normal window and one private window, so you can be a teacher and a student at once.
#	Do this	Expected
1	Open /register	A “student” / “teacher” card picker, with student selected
2	Submit with the name blank, or password abc	Inline message under the field and focus moves to it. Nothing is sent
3	Register as a teacher	Signed in automatically, Home shows “Welcome, <name>“ and Join class and Create class buttons
4	Register the same email again	Red alert: “Email already registered”
5	Click Create class, submit with a blank name	“Class name is required.” and the dialog stays open
6	Create “Math 101” with a section and subject	The dialog closes and you land on /classes/<id>. The sidebar shows the join code
7	Go back to Home	The class card is there with a “teacher” badge and the code
8	In the other browser, register as a student	Home shows only Join class (no Create button)
9	Click Join class, type the code in lowercase with a space	It is upper-cased and the space is dropped. Submit joins and opens the class. The sidebar shows no join code
10	Join the same class again	Red alert: “You are already a member of this classroom”
11	Join with NOPE999	Red alert: “Invalid join code”
12	Join with a! or ab	“Enter the 4-16 letter or digit code…” and no request is sent
13	As the teacher, archive the class (PATCH /classrooms/{id} {"is_archived": true} in Swagger) and reload Classes	The card disappears. Tick Show archived classes and it returns with an “Archived” badge
14	Press Esc or click Cancel on a dialog	It closes and the fields are cleared when you reopen it
15	Stop the backend and click Try again on the empty list	A “Cannot reach the server” alert, no crash
16	Open /register, then use a throttled network and click Create account several times	One request only (the button is disabled while submitting)
3. Expected API traffic (Network tab)
Action	Requests
Register	POST /auth/register 201, POST /auth/login 200, GET /auth/me 200
Home	GET /classrooms?include_archived=false&limit=100 200
Create	POST /classrooms 201, then a list refetch
Join	POST /classrooms/join 200, then a list refetch
Create as a student	The button is hidden. The API would return 403
Expired access token	The failing call 401, then one POST /auth/refresh 200, then the call repeats 200
Troubleshooting
Problem	Fix
Cannot find module '@radix-ui/react-dialog'	Run npm install @radix-ui/react-dialog in frontend/
Cannot find module '@/pages/Login' or similar	The old pages/auth/* and HomePage.tsx were not removed or the new files were not created. Re-check the tree above
Module 'lucide-react' has no exported member 'School'	Your lucide version is older. Run npm update lucide-react, or swap School for Users in Register.tsx
403 when creating a class	The account’s global role is student. Register a new account as a teacher
429 on login or join	Login is 10/min and join is 10/min per IP. Wait a minute
New class does not appear on Home	The classroom lists use include_archived=false. A class you archived shows only with the checkbox ticked
Dialog does not close on Esc	A request is in flight. Dialogs can’t close until it finishes, by design
Reply NEXT for STEP 15.
STEP 15 — Classroom Detail (Stream Tab)
text
STEP 15: Classroom detail page with tabs (Stream | Classwork | People | Grades).

- Route: /classrooms/:id
- Header: class name, section, join code (teachers only, copy button)
- Stream tab: announcements list (create form for teachers), comments drawer.
- Classwork tab: sections for Assignments, Quizzes, Materials (create buttons for teachers).
- People tab: teachers/students lists.
- Wire to backend endpoints from STEPs 6, 8, 9, 10, 11.
```