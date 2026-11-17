import { CheckCircle2, GraduationCap } from "lucide-react";
import type { ReactNode } from "react";

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
}

const HIGHLIGHTS = [
  "Announcements, assignments and quizzes in one place",
  "Turn in work with notes and attachments",
  "Speaks every result aloud for Blind Mode",
];

/** Split brand panel + form card, used by the login and register pages. */
export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden p-4">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0">
        <div className="absolute -left-24 -top-24 h-72 w-72 rounded-full bg-primary/15 blur-3xl" />
        <div className="absolute -bottom-32 -right-20 h-80 w-80 rounded-full bg-[hsl(258_70%_50%/0.12)] blur-3xl" />
      </div>

      <div className="relative grid w-full max-w-4xl overflow-hidden rounded-2xl border bg-card shadow-xl sm:grid-cols-[1.05fr_1fr]">
        <section aria-label="About Noor LMS" className="hidden flex-col justify-between gap-8 bg-brand p-6 text-primary-foreground sm:flex lg:p-8">
          <div className="flex items-center gap-2 text-lg font-bold tracking-tight">
            <span className="grid h-9 w-9 place-items-center rounded-xl bg-white/15">
              <GraduationCap className="h-5 w-5" aria-hidden="true" />
            </span>
            Noor LMS
          </div>

          <div className="space-y-4">
            <p className="text-3xl font-semibold leading-snug">Class, without the clutter.</p>
            <p className="max-w-xs text-sm leading-relaxed">
              A calm place for your class to read, hand in work and take quizzes — built to work with
              a keyboard and a screen reader alone.
            </p>
            <ul className="space-y-2 text-sm">
              {HIGHLIGHTS.map((item) => (
                <li key={item} className="flex items-start gap-2">
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
                  {item}
                </li>
              ))}
            </ul>
          </div>

          <p className="text-xs">Noor LMS · a calmer learning space</p>
        </section>

        <div className="p-6 sm:p-8">
          <div className="mb-6 flex items-center gap-2 text-lg font-bold tracking-tight sm:hidden">
            <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-primary-foreground">
              <GraduationCap className="h-5 w-5" aria-hidden="true" />
            </span>
            Noor LMS
          </div>

          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-muted-foreground">{description}</p>

          <div className="mt-6">{children}</div>

          {footer ? <div className="mt-6 text-sm text-muted-foreground">{footer}</div> : null}
        </div>
      </div>
    </main>
  );
}
