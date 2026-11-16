import { Plus } from "lucide-react";
import { useCallback, useState, type ChangeEvent } from "react";

import { FormDialog } from "@/components/common/FormDialog";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { useCreateQuiz } from "@/features/quizzes/hooks";
import { useFormDialog } from "@/hooks/useFormDialog";
import type { QuizCreateInput } from "@/types";

const EMPTY = { title: "", description: "", minutes: "", retake: false };
type FormState = typeof EMPTY;
type Errors = { title?: string; minutes?: string };

/** Creates a DRAFT quiz. The question editor arrives with the quiz pages. */
export function CreateQuizDialog({ classroomId }: { classroomId: string }) {
  const create = useCreateQuiz(classroomId);
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
    const minutesText = form.minutes.trim();
    const minutes = Number(minutesText);

    const next: Errors = {};
    if (!title) next.title = "Title is required.";
    if (minutesText && (!Number.isInteger(minutes) || minutes < 1 || minutes > 600)) {
      next.minutes = "Enter a whole number of minutes from 1 to 600, or leave it empty.";
    }
    setErrors(next);
    const firstInvalid = next.title ? "quiz-title" : next.minutes ? "quiz-minutes" : null;
    if (firstInvalid) {
      document.getElementById(firstInvalid)?.focus();
      return false;
    }

    const body: QuizCreateInput = { title, published: false, allow_retake: form.retake };
    const description = form.description.trim();
    if (description) body.description = description;
    if (minutesText) body.time_limit_minutes = minutes;
    create.mutate(body, { onSuccess: dialog.close });
  }

  return (
    <FormDialog
      open={dialog.open}
      onOpenChange={dialog.onOpenChange}
      trigger={
        <Button>
          <Plus aria-hidden="true" />
          Create quiz
        </Button>
      }
      title="Create a quiz"
      description="The quiz is saved as a draft. Adding questions and publishing it comes with the quiz editor."
      submitLabel="Create draft"
      pendingLabel="Creating…"
      isPending={create.isPending}
      error={create.isError ? create.error : null}
      onSubmit={onSubmit}
    >
      <TextField
        id="quiz-title"
        label="Title"
        required
        maxLength={255}
        autoComplete="off"
        value={form.title}
        onChange={bind("title")}
        error={errors.title}
      />
      <TextAreaField
        id="quiz-description"
        label="Description"
        rows={3}
        maxLength={10_000}
        value={form.description}
        onChange={bind("description")}
      />
      <TextField
        id="quiz-minutes"
        label="Time limit (minutes)"
        type="number"
        inputMode="numeric"
        min={1}
        max={600}
        step={1}
        hint="Leave empty for no time limit."
        value={form.minutes}
        onChange={bind("minutes")}
        error={errors.minutes}
      />
      <label className="flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          className="h-4 w-4 accent-primary"
          checked={form.retake}
          onChange={(e) => setForm((current) => ({ ...current, retake: e.target.checked }))}
        />
        Allow students to retake the quiz
      </label>
    </FormDialog>
  );
}
