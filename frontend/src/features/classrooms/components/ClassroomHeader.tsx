import { ArrowLeft, Check, Copy } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCopyToClipboard } from "@/hooks/useCopyToClipboard";
import type { Classroom } from "@/types";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function ClassroomHeader({ classroom }: { classroom: Classroom }) {
  const { copied, copy } = useCopyToClipboard();
  const [copyFailed, setCopyFailed] = useState(false);
  const joinCode = classroom.join_code;

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
        className="inline-flex items-center gap-1 rounded text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All classes
      </Link>

      <div className="relative overflow-hidden rounded-2xl border bg-card p-5 shadow-sm sm:p-6">
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1.5 bg-brand" />
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="flex min-w-0 items-start gap-4">
            <span
              aria-hidden="true"
              className="grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-brand text-lg font-bold text-primary-foreground shadow-sm"
            >
              {initials(classroom.name)}
            </span>
            <div className="min-w-0">
              <h1 className="break-words text-2xl font-semibold tracking-tight">{classroom.name}</h1>
              {details ? <p className="mt-0.5 text-muted-foreground">{details}</p> : null}
              <div className="mt-2 flex flex-wrap gap-2">
                <Badge className="capitalize">{classroom.my_role}</Badge>
                {classroom.is_archived ? <Badge variant="destructive">Archived</Badge> : null}
              </div>
            </div>
          </div>

          {joinCode ? (
            <div className="rounded-xl border border-primary/20 bg-primary/5 p-3 transition-colors hover:border-primary/40">
              <p className="text-xs text-muted-foreground">Join code (share with your students)</p>
              <div className="mt-1 flex items-center gap-3">
                <code className="select-all text-xl font-semibold tracking-widest">{joinCode}</code>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  aria-label={`Copy join code ${joinCode}`}
                  onClick={() => void onCopy(joinCode)}
                >
                  {copied ? <Check aria-hidden="true" /> : <Copy aria-hidden="true" />}
                  {copied ? "Copied" : "Copy"}
                </Button>
              </div>
              <p role="status" className="mt-1 min-h-4 text-xs text-muted-foreground">
                {copied
                  ? "Join code copied to the clipboard."
                  : copyFailed
                    ? "Could not copy. Select the code and copy it manually."
                    : ""}
              </p>
            </div>
          ) : null}
        </div>
      </div>

      {classroom.is_archived ? (
        <p role="note" className="rounded-xl border border-destructive/40 bg-destructive/10 p-3 text-sm">
          This class is archived and read-only. Unarchive it to post, grade or change anything.
        </p>
      ) : null}
    </header>
  );
}
