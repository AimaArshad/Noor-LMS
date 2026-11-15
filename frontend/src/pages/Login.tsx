import { useRef, useState, type FormEvent } from "react";
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
  const inFlight = useRef(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (inFlight.current) return;
    setError(null);
    inFlight.current = true;
    setSubmitting(true);
    try {
      await login({ email: email.trim(), password });
      // GuestRoute redirects (to the page you came from, or Home) once the store has a user.
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  }

  return (
    <AuthShell
      title="Sign in"
      description="Use your Noor LMS account."
      footer={
        <>
          No account?{" "}
          <Link to="/register" state={location.state} className="text-primary underline-offset-4 hover:underline">
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
