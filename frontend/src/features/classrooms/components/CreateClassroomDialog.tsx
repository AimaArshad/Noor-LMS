import { Plus } from "lucide-react";
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
  // Guards two submit events in the same tick, before `isPending` has re-rendered the button.
  const inFlight = useRef(false);

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
    if (inFlight.current) return;
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
    inFlight.current = true;
    create.mutate(body, {
      onSuccess: (classroom) => {
        setOpen(false);
        setForm(EMPTY);
        navigate(`/classes/${classroom.id}`, {
          state: { announcement: `Class “${classroom.name}” created.` },
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
        <Button>
          <Plus aria-hidden="true" />
          Create class
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create a class</DialogTitle>
          <DialogDescription>You will get a join code to share with your students.</DialogDescription>
        </DialogHeader>

        <form onSubmit={onSubmit} className="space-y-4">
          <p role="status" className="sr-only">
            {create.isPending ? "Creating the class…" : ""}
          </p>
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
