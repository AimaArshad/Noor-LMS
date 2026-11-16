import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateMaterial } from "@/features/materials/hooks";
import { useFormDialog } from "@/hooks/useFormDialog";
import type { MaterialCreateInput } from "@/types";

const EMPTY = { title: "", description: "" };
type FormState = typeof EMPTY;

export function CreateMaterialDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateMaterial(classroomId);
  const { reset: resetMutation } = create;
  const [form, setForm] = useState<FormState>(EMPTY);
  const [titleError, setTitleError] = useState<string | null>(null);

  const resetAll = useCallback(() => {
    setForm(EMPTY);
    setTitleError(null);
    resetMutation();
  }, [resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  const bind = (key: keyof FormState) => (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  function onSubmit(): boolean | void {
    const title = form.title.trim();
    if (!title) {
      setTitleError("Title is required.");
      document.getElementById("material-title")?.focus();
      return false;
    }
    setTitleError(null);
    const body: MaterialCreateInput = { title };
    const description = form.description.trim();
    if (description) body.description = description;
    create.mutate(body, { onSuccess: dialog.close });
  }

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Add material
        </Button>
      }
      title="Add a material"
      description="Students are notified. File attachments come with the file picker step."
      submitLabel="Post"
      pendingLabel="Posting…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={onSubmit}
    >
      <TextField
        id="material-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={titleError}
      />
      <TextAreaField
        id="material-description"
        label="Description"
        rows={4}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
    </FormDialog>
  );
}
