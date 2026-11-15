import type { ReactNode } from "react";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

interface AuthShellProps {
  title: string;
  description: string;
  children: ReactNode;
  footer?: ReactNode;
}

/** Centered card used by the login and register pages. */
export function AuthShell({ title, description, children, footer }: AuthShellProps) {
  return (
    <main className="flex min-h-screen items-center justify-center bg-muted/40 p-4">
      <div className="w-full max-w-md">
        <p className="mb-4 text-center text-2xl font-bold tracking-tight">Noor LMS</p>
        <Card>
          <CardHeader>
            <CardTitle>
              <h1 className="text-xl font-semibold leading-none tracking-tight">{title}</h1>
            </CardTitle>
            <CardDescription>{description}</CardDescription>
          </CardHeader>
          <CardContent>{children}</CardContent>
        </Card>
        {footer ? <p className="mt-4 text-center text-sm text-muted-foreground">{footer}</p> : null}
      </div>
    </main>
  );
}
