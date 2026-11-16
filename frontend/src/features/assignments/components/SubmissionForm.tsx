import { zodResolver } from "@hookform/resolvers/zod";
import { CheckCircle2 } from "lucide-react";
import { Controller, useForm } from "react-hook-form";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { FileDropzone } from "@/components/common/FileDropzone";
import { TextAreaField } from "@/components/common/TextAreaField";
import { Button } from "@/components/ui/button";
import { useSubmitAssignment } from "@/features/assignments/hooks";
import { submissionFormSchema, type SubmissionFormValues } from "@/features/assignments/schemas";
import type { Submission } from "@/types";

interface SubmissionFormProps {
  assignmentId: string;
  /** The existing submission, if any (the form starts with its content). */
  submission: Submission | null | undefined;
  disabled: boolean;
}

/** Mount this only after the submission query has resolved: it reads the initial values once. */
export function SubmissionForm({ assignmentId, submission, disabled }: SubmissionFormProps) {
  const submit = useSubmitAssignment(assignmentId);
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = useForm<SubmissionFormValues>({
    resolver: zodResolver(submissionFormSchema),
    defaultValues: {
      content: submission?.content ?? "",
      attachments: submission?.attachments ?? [],
    },
  });

  const resubmitting = submission !== null && submission !== undefined;
  const afterReturn = submission?.state === "returned";

  const onValid = handleSubmit((values) => {
    submit.mutate({
      content: values.content.trim() || undefined,
      attachments: values.attachments,
    });
  });

  return (
    <form onSubmit={(e) => void onValid(e)} noValidate className="space-y-4">
      <h2 className="text-lg font-semibold">{resubmitting ? "Update your work" : "Turn in your work"}</h2>
      {afterReturn ? (
        <p role="note" className="rounded-md border bg-secondary p-3 text-sm">
          Resubmitting clears your current grade. Your teacher will grade the new version.
        </p>
      ) : null}
      {disabled ? (
        <p role="note" className="rounded-md border bg-secondary p-3 text-sm">
          This class is archived, so work can no longer be submitted.
        </p>
      ) : null}

      <ErrorAlert message={submit.isError ? getErrorMessage(submit.error) : null} />

      <TextAreaField
        id="submission-content"
        label="Your answer"
        rows={6}
        maxLength={20_000}
        disabled={disabled || submit.isPending}
        {...register("content")}
        error={errors.content?.message}
      />
      <Controller
        control={control}
        name="attachments"
        render={({ field }) => (
          <FileDropzone
            id="submission-files"
            label="Attachments"
            value={field.value}
            onChange={field.onChange}
            disabled={disabled || submit.isPending}
            error={errors.attachments?.message}
          />
        )}
      />

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" disabled={disabled || submit.isPending}>
          {submit.isPending ? "Submitting…" : resubmitting ? "Resubmit" : "Turn in"}
        </Button>
        <p role="status" className="flex items-center gap-1 text-sm text-muted-foreground">
          {submit.isSuccess ? (
            <>
              <CheckCircle2 className="h-4 w-4 text-primary" aria-hidden="true" />
              Your work was turned in.
            </>
          ) : null}
        </p>
      </div>
    </form>
  );
}
