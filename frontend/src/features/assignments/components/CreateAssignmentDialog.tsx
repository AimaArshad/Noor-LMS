import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateAssignment } from "@/features/assignments/hooks";
import { useFormDialog } from "@/hooks/useFormDialog";
import { toIsoFromLocalInput } from "@/lib/format";
import type { AssignmentCreateInput } from "@/types";

const EMPTY = { title: "", description: "", due: "", points: "100", publish: false };
type FormState = typeof EMPTY;
type Errors = { title?: string; points?: string; due?: string };

export function CreateAssignmentDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateAssignment(classroomId);
  const { reset: resetMutation } = create;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [errors, setErrors] = useState<Errors>({});

  const resetAll = useCallback(() => {
    setForm(EMPTY);
    setErrors({});
    resetMutation();
  }, [resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit(): boolean | void {
    const title = form.title.trim();
    const points = Number(form.points);
    const dueAt = toIsoFromLocalInput(form.due);

    const next: Errors = {};
    if (!title) next.title = "Title is required.";
    if (!Number.isInteger(points) || points < 1 || points > 100_000) {
      next.points = "Enter a whole number from 1 to 100000.";
    }
    if (form.due && !dueAt) next.due = "Enter a valid date and time.";
    setErrors(next);

    const firstInvalid = next.title
      ? "assignment-title"
      : next.points
        ? "assignment-points"
        : next.due
          ? "assignment-due"
          : null;
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus();
      return false;
    }

    const body: AssignmentCreateInput = {
      title,
      max_points: points,
      state: form.publish ? "published" : "draft",
    };
    const description = form.description.trim();
    if (description) body.description = description;
    if (dueAt) body.due_at = dueAt;
    create.mutate(body, { onSuccess: dialog.close });
  }

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Create assignment
        </Button>
      }
      title="Create an assignment"
      description="Save it as a draft, or publish it so students see it and get it on their to-do list."
      submitLabel="Create"
      pendingLabel="Creating…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={onSubmit}
    >
      <TextField
        id="assignment-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={errors.title}
      />
      <TextAreaField
        id="assignment-description"
        label="Instructions"
        rows={4}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          id="assignment-due"
          label="Due date"
          type="datetime-local"
          value={form.due}
          onChange={bind("due")}
          error={errors.due}
        />
        <TextField
          id="assignment-points"
          label="Points"
          type="number"
          inputMode="numeric"
          min={1}
          max={100_000}
          step={1}
          value={form.points}
          onChange={bind("points")}
          error={errors.points}
        />
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={form.publish}
          onChange={(e) => setForm((current) => ({ ...current, publish: e.target.checked }))}
        />
        Publish now
      </label>
    </FormDialog>
  );
}
