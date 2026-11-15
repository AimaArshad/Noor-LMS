import { LogIn } from "lucide-react";
import { useRef, useState, type ChangeEvent, type FormEvent } from "react";
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
  // Guards two submit events in the same tick, before `isPending` has re-rendered the button.
  const inFlight = useRef(false);

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
    if (inFlight.current) return;
    if (!CODE_PATTERN.test(code)) {
      setCodeError("Enter the 4-16 letter or digit code from your teacher.");
      document.getElementById("join-code")?.focus();
      return;
    }
    inFlight.current = true;
    join.mutate(code, {
      onSuccess: (classroom) => {
        setOpen(false);
        setCode("");
        navigate(`/classes/${classroom.id}`, {
          state: { announcement: `You joined “${classroom.name}”.` },
        });
      },
      onSettled: () => {
        inFlight.current = false;
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
          <p role="status" className="sr-only">
            {join.isPending ? "Joining the class…" : ""}
          </p>
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
