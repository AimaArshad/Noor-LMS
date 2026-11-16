import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { FormProvider, useFieldArray, useForm, useWatch } from "react-hook-form";
import { Link, useNavigate } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { TextAreaField } from "@/components/common/TextAreaField";
import { TextField } from "@/components/common/TextField";
import { Button } from "@/components/ui/button";
import { QuestionEditor } from "@/features/quizzes/components/QuestionEditor";
import { useCreateQuiz } from "@/features/quizzes/hooks";
import {
  MAX_QUESTIONS,
  newQuestion,
  quizFormSchema,
  toPayload,
  type QuizFormValues,
} from "@/features/quizzes/schemas";
import { arrayError } from "@/lib/forms";
import { formatPoints } from "@/lib/format";
import type { Classroom } from "@/types";

export function QuizBuilder({ classroom }: { classroom: Classroom }) {
  const navigate = useNavigate();
  const create = useCreateQuiz(classroom.id);
  const form = useForm<QuizFormValues>({
    resolver: zodResolver(quizFormSchema),
    defaultValues: {
      title: "",
      description: "",
      minutes: "",
      due: "",
      allowRetake: false,
      publish: false,
      questions: [newQuestion()],
    },
  });
  const {
    register,
    control,
    handleSubmit,
    formState: { errors },
  } = form;
  const questions = useFieldArray({ control, name: "questions" });
  const watched = useWatch({ control, name: "questions" });
  const total = (watched ?? []).reduce((sum, q) => sum + (Number(q?.points) || 0), 0);

  const onValid = handleSubmit((values) => {
    create.mutate(toPayload(values), {
      onSuccess: (quiz) => navigate(`/classes/${classroom.id}/quizzes/${quiz.id}`),
    });
  });

  return (
    <FormProvider {...form}>
      <form onSubmit={(e) => void onValid(e)} noValidate className="mx-auto max-w-3xl space-y-6">
        <header>
          <h2 className="text-2xl font-semibold tracking-tight">Create a quiz</h2>
          <p className="text-sm text-muted-foreground">
            Multiple-choice and true/false questions are graded automatically; short answers too, when
            you list accepted answers.
          </p>
        </header>

        <ErrorAlert message={create.isError ? getErrorMessage(create.error) : null} />

        <TextField
          id="quiz-title"
          label="Title"
          required
          autoComplete="off"
          {...register("title")}
          error={errors.title?.message}
        />
        <TextAreaField
          id="quiz-description"
          label="Description"
          rows={3}
          {...register("description")}
          error={errors.description?.message}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <TextField
            id="quiz-minutes"
            label="Time limit (minutes)"
            inputMode="numeric"
            autoComplete="off"
            hint="Leave empty for no time limit."
            {...register("minutes")}
            error={errors.minutes?.message}
          />
          <TextField
            id="quiz-due"
            label="Due date"
            type="datetime-local"
            {...register("due")}
            error={errors.due?.message}
          />
        </div>
        <div className="space-y-2">
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" {...register("allowRetake")} />
            Allow students to retake the quiz
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="h-4 w-4 accent-primary" {...register("publish")} />
            Publish now (students see it and get it on their to-do list)
          </label>
        </div>

        <section aria-labelledby="questions-title" className="space-y-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h3 id="questions-title" className="text-lg font-semibold">
              Questions
            </h3>
            <p className="text-sm text-muted-foreground">
              {questions.fields.length} question{questions.fields.length === 1 ? "" : "s"} ·{" "}
              {formatPoints(total)} points in total
            </p>
          </div>
          {arrayError(errors.questions) ? (
            <p role="alert" className="text-sm text-destructive">
              {arrayError(errors.questions)}
            </p>
          ) : null}

          {questions.fields.map((field, index) => (
            <QuestionEditor
              key={field.id}
              index={index}
              total={questions.fields.length}
              onRemove={() => questions.remove(index)}
              onMove={(to) => questions.move(index, to)}
            />
          ))}

          <Button
            type="button"
            variant="outline"
            disabled={questions.fields.length >= MAX_QUESTIONS}
            onClick={() => questions.append(newQuestion(), { shouldFocus: false })}
          >
            <Plus aria-hidden="true" />
            Add question
          </Button>
        </section>

        <div className="flex flex-wrap justify-end gap-2 border-t pt-4">
          <Button asChild variant="outline">
            <Link to={`/classes/${classroom.id}/classwork`}>Cancel</Link>
          </Button>
          <Button type="submit" disabled={create.isPending}>
            {create.isPending ? "Saving…" : "Save quiz"}
          </Button>
        </div>
      </form>
    </FormProvider>
  );
}
