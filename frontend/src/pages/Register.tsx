import { GraduationCap, School, type LucideIcon } from "lucide-react";
import { useRef, useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

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
  const location = useLocation();
  const login = useAuthStore((s) => s.login);

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<Role>("student");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  // `submitting` only disables the button on the next render; this ref also swallows a second
  // submit event that arrives in the same tick (keyboard + click, or a scripted double click).
  const inFlight = useRef(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
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
    inFlight.current = true;
    setSubmitting(true);
    try {
      await authApi.register({ ...credentials, full_name: fullName.trim(), role });
    } catch (err) {
      setError(getErrorMessage(err));
      inFlight.current = false;
      setSubmitting(false);
      return;
    }

    try {
      await login(credentials); // GuestRoute then redirects (to `from`, or Home)
    } catch {
      // The account exists; only the automatic sign-in failed (e.g. rate limit).
      navigate("/login", {
        replace: true,
        state: { ...(location.state as object | null), notice: "Account created. Please sign in." },
      });
    } finally {
      inFlight.current = false;
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
          <Link to="/login" state={location.state} className="text-primary underline-offset-4 hover:underline">
            Sign in
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        <p role="status" className="sr-only">
          {submitting ? "Creating your account…" : ""}
        </p>
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
