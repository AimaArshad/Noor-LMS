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

        {joinCode ? (
          <div className="rounded-lg border p-3">
            <p className="text-xs text-muted-foreground">Join code (share with your students)</p>
            <div className="mt-1 flex items-center gap-3">
              <code className="text-xl font-semibold tracking-widest">{joinCode}</code>
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

      {classroom.is_archived ? (
        <p role="note" className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm">
          This class is archived and read-only. Unarchive it to post, grade or change anything.
        </p>
      ) : null}
    </header>
  );
}
