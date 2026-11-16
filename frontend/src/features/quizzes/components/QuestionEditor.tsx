import { ArrowDown, ArrowUp, Plus, Trash2 } from "lucide-react";
import { useFieldArray, useFormContext, useWatch } from "react-hook-form";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { MAX_OPTIONS, type QuizFormValues } from "@/features/quizzes/schemas";
import { arrayError } from "@/lib/forms";
import type { QuestionType } from "@/types";

interface QuestionEditorProps {
  index: number;
  total: number;
  onRemove: () => void;
  onMove: (to: number) => void;
}

const TYPE_LABEL: Record<QuestionType, string> = {
  mcq: "Multiple choice",
  true_false: "True / False",
  short_answer: "Short answer",
};

const SELECT_CLASS =
  "flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function QuestionEditor({ index, total, onRemove, onMove }: QuestionEditorProps) {
  const {
    register,
    control,
    setValue,
    formState: { errors },
  } = useFormContext<QuizFormValues>();
  const options = useFieldArray({ control, name: `questions.${index}.options` });
  const type = useWatch({ control, name: `questions.${index}.type` });
  const correct = useWatch({ control, name: `questions.${index}.correctIndex` });
  const qErr = errors.questions?.[index];
  const n = index + 1;

  function onTypeChange(next: QuestionType) {
    setValue(`questions.${index}.correctIndex`, 0);
    if (next === "true_false") options.replace([{ text: "True" }, { text: "False" }]);
    else if (next === "mcq") options.replace([{ text: "" }, { text: "" }]);
    else options.replace([]);
  }

  function removeOption(position: number) {
    options.remove(position);
    const next = position < correct ? correct - 1 : position === correct ? 0 : correct;
    setValue(`questions.${index}.correctIndex`, next, { shouldDirty: true });
  }

  return (
    <Card>
      <CardContent className="space-y-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold">Question {n}</h3>
          <div className="flex gap-1">
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={index === 0}
              onClick={() => onMove(index - 1)}
            >
              <ArrowUp aria-hidden="true" />
              <span className="sr-only">Move question {n} up</span>
            </Button>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              disabled={index === total - 1}
              onClick={() => onMove(index + 1)}
            >
              <ArrowDown aria-hidden="true" />
              <span className="sr-only">Move question {n} down</span>
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={onRemove}>
              <Trash2 aria-hidden="true" />
              <span className="sr-only">Delete question {n}</span>
            </Button>
          </div>
        </div>

        <div className="grid gap-4 sm:grid-cols-[1fr_8rem]">
          <div className="space-y-2">
            <Label htmlFor={`q${index}-type`}>Type</Label>
            <select
              id={`q${index}-type`}
              className={SELECT_CLASS}
              {...register(`questions.${index}.type`, {
                onChange: (e) => onTypeChange(e.target.value as QuestionType),
              })}
            >
              {(Object.keys(TYPE_LABEL) as QuestionType[]).map((value) => (
                <option key={value} value={value}>
                  {TYPE_LABEL[value]}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-2">
            <Label htmlFor={`q${index}-points`}>Points</Label>
            <Input
              id={`q${index}-points`}
              inputMode="decimal"
              autoComplete="off"
              aria-invalid={qErr?.points ? true : undefined}
              {...register(`questions.${index}.points`)}
            />
          </div>
        </div>
        {qErr?.points ? (
          <p role="alert" className="-mt-2 text-sm text-destructive">
            {qErr.points.message}
          </p>
        ) : null}

        <div className="space-y-2">
          <Label htmlFor={`q${index}-prompt`}>Question</Label>
          <Textarea
            id={`q${index}-prompt`}
            rows={2}
            aria-invalid={qErr?.prompt ? true : undefined}
            {...register(`questions.${index}.prompt`)}
          />
          {qErr?.prompt ? (
            <p role="alert" className="text-sm text-destructive">
              {qErr.prompt.message}
            </p>
          ) : null}
        </div>

        {type === "true_false" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Correct answer</legend>
            {["True", "False"].map((label, value) => (
              <label key={label} className="flex items-center gap-2 text-sm">
                <input
                  type="radio"
                  name={`q${index}-correct`}
                  className="h-4 w-4 accent-primary"
                  checked={correct === value}
                  onChange={() => setValue(`questions.${index}.correctIndex`, value, { shouldDirty: true })}
                />
                {label}
              </label>
            ))}
          </fieldset>
        ) : null}

        {type === "mcq" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Options (select the correct one)</legend>
            {options.fields.map((field, position) => {
              const optionError = qErr?.options?.[position]?.text?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <input
                      type="radio"
                      name={`q${index}-correct`}
                      className="h-4 w-4 shrink-0 accent-primary"
                      aria-label={`Mark option ${position + 1} of question ${n} as correct`}
                      checked={correct === position}
                      onChange={() =>
                        setValue(`questions.${index}.correctIndex`, position, {
                          shouldDirty: true,
                          shouldValidate: true,
                        })
                      }
                    />
                    <Input
                      aria-label={`Question ${n}, option ${position + 1}`}
                      aria-invalid={optionError ? true : undefined}
                      autoComplete="off"
                      {...register(`questions.${index}.options.${position}.text`)}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      disabled={options.fields.length <= 2}
                      onClick={() => removeOption(position)}
                    >
                      <Trash2 aria-hidden="true" />
                      <span className="sr-only">Remove option {position + 1}</span>
                    </Button>
                  </div>
                  {optionError ? (
                    <p role="alert" className="ml-6 text-sm text-destructive">
                      {optionError}
                    </p>
                  ) : null}
                </div>
              );
            })}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={options.fields.length >= MAX_OPTIONS}
              onClick={() => options.append({ text: "" }, { shouldFocus: true })}
            >
              <Plus aria-hidden="true" />
              Add option
            </Button>
          </fieldset>
        ) : null}

        {type === "short_answer" ? (
          <fieldset className="space-y-2">
            <legend className="text-sm font-medium">Accepted answers (optional)</legend>
            <p className="text-xs text-muted-foreground">
              Matching ignores case and extra spaces. Leave empty to grade this question by hand.
            </p>
            {options.fields.map((field, position) => {
              const optionError = qErr?.options?.[position]?.text?.message;
              return (
                <div key={field.id} className="space-y-1">
                  <div className="flex items-center gap-2">
                    <Input
                      aria-label={`Question ${n}, accepted answer ${position + 1}`}
                      aria-invalid={optionError ? true : undefined}
                      autoComplete="off"
                      {...register(`questions.${index}.options.${position}.text`)}
                    />
                    <Button type="button" variant="ghost" size="sm" onClick={() => options.remove(position)}>
                      <Trash2 aria-hidden="true" />
                      <span className="sr-only">Remove accepted answer {position + 1}</span>
                    </Button>
                  </div>
                  {optionError ? (
                    <p role="alert" className="text-sm text-destructive">
                      {optionError}
                    </p>
                  ) : null}
                </div>
              );
            })}
            <Button
              type="button"
              variant="outline"
              size="sm"
              disabled={options.fields.length >= MAX_OPTIONS}
              onClick={() => options.append({ text: "" }, { shouldFocus: true })}
            >
              <Plus aria-hidden="true" />
              Add accepted answer
            </Button>
          </fieldset>
        ) : null}

        {arrayError(qErr?.options) ? (
          <p role="alert" className="text-sm text-destructive">
            {arrayError(qErr?.options)}
          </p>
        ) : null}
        {qErr?.correctIndex ? (
          <p role="alert" className="text-sm text-destructive">
            {qErr.correctIndex.message}
          </p>
        ) : null}
      </CardContent>
    </Card>
  );
}
