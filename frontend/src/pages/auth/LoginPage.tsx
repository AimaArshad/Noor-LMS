import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { AuthShell } from "@/components/layout/AuthShell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function LoginPage() {
  useDocumentTitle("Sign in");
  const login = useAuthStore((s) => s.login);
  const location = useLocation();
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
      // GuestRoute redirects once the store has a user.
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
          <Link to="/register" state={location.state} className="text-primary underline-offset-4 hover:underline">
            Create one
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-4">
        {error ? (
          <p role="alert" className="rounded-md border border-destructive/50 bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </p>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input
            id="email"
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>
        <Button type="submit" className="w-full" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </AuthShell>
  );
}
