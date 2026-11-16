import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useCallback } from "react";
import { Controller, useForm } from "react-hook-form";

import { FileDropzone } from "@/components/common/FileDropzone";
import { FormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import type { AssignmentPayload } from "@/features/assignments/api";
import { useCreateAssignment } from "@/features/assignments/hooks";
import { assignmentFormSchema, type AssignmentFormValues } from "@/features/assignments/schemas";
import { useFormDialog } from "@/hooks/useFormDialog";
import { toIsoFromLocalInput } from "@/lib/format";

const DEFAULTS: AssignmentFormValues = {
  title: "",
  description: "",
  due: "",
  points: "100",
  publish: false,
  attachments: [],
};

export function CreateAssignmentDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateAssignment(classroomId);
  const { reset: resetMutation } = create;
  const {
    register,
    control,
    getValues,
    trigger,
    setFocus,
    reset,
    formState: { errors },
  } = useForm<AssignmentFormValues>({
    resolver: zodResolver(assignmentFormSchema),
    defaultValues: DEFAULTS,
  });

  const resetAll = useCallback(() => {
    reset(DEFAULTS);
    resetMutation();
  }, [reset, resetMutation]);
  const dialog = useFormDialog({ isPending: create.isPending, onReset: resetAll });

  // FormDialog needs to know *now* whether a request was sent: `handleSubmit` validates
  // asynchronously, so validate synchronously and let `trigger` render the messages.
  function submit(): boolean {
    const parsed = assignmentFormSchema.safeParse(getValues());
    if (!parsed.success) {
      const field = parsed.error.issues[0]?.path[0];
      if (typeof field === "string") void setFocus(field as keyof AssignmentFormValues);
      void trigger();
      return false;
    }
    const values = parsed.data as AssignmentFormValues;
    const body: AssignmentPayload = {
      title: values.title,
      max_points: Number(values.points),
      state: values.publish ? "published" : "draft",
      attachments: values.attachments,
    };
    if (values.description) body.description = values.description;
    const dueAt = toIsoFromLocalInput(values.due);
    if (dueAt) body.due_at = dueAt;
    create.mutate(body, { onSuccess: dialog.close });
    return true;
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
      onSubmit={submit}
    >
      <TextField
        id="assignment-title"
        label="Title"
        required
        autoComplete="off"
        {...register("title")}
        error={errors.title?.message}
      />
      <TextAreaField
        id="assignment-description"
        label="Instructions"
        rows={4}
        {...register("description")}
        error={errors.description?.message}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <TextField
          id="assignment-due"
          label="Due date"
          type="datetime-local"
          {...register("due")}
          error={errors.due?.message}
        />
        <TextField
          id="assignment-points"
          label="Points"
          inputMode="numeric"
          autoComplete="off"
          {...register("points")}
          error={errors.points?.message}
        />
      </div>
      <Controller
        control={control}
        name="attachments"
        render={({ field }) => (
          <FileDropzone
            id="assignment-files"
            label="Attachments"
            value={field.value}
            onChange={field.onChange}
            disabled={create.isPending}
            error={errors.attachments?.message}
          />
        )}
      />
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" className="h-4 w-4 accent-primary" {...register("publish")} />
        Publish now
      </label>
    </FormDialog>
  );
}
