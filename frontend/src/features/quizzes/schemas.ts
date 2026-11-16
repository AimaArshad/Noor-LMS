import { z } from "zod";

import { toIsoFromLocalInput } from "@/lib/format";
import type { QuizCreatePayload, QuestionType } from "@/types";

export const MAX_QUESTIONS = 200;
export const MAX_OPTIONS = 10;
const MAX_TOTAL_POINTS = 99_999.99;

const optionSchema = z.object({
  text: z.string().trim().min(1, "Enter the text.").max(1000, "At most 1000 characters."),
});

const questionSchema = z
  .object({
    type: z.enum(["mcq", "true_false", "short_answer"]),
    prompt: z.string().trim().min(1, "Enter the question.").max(5000, "At most 5000 characters."),
    points: z
      .string()
      .trim()
      .regex(/^\d{1,4}(\.\d{1,2})?$/, "Enter a number up to 9999.99 (2 decimals at most).")
      .refine((v) => Number(v) > 0, "Points must be greater than 0."),
    /** Index of the correct option (mcq / true_false). Ignored for short answers. */
    correctIndex: z.number().int().min(0),
    options: z.array(optionSchema).max(MAX_OPTIONS, `At most ${MAX_OPTIONS} options.`),
  })
  .superRefine((q, ctx) => {
    const texts = q.options.map((o) => o.text.trim().toLocaleLowerCase()).filter(Boolean);
    if (new Set(texts).size !== texts.length) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["options"], message: "Each option must be different." });
    }
    if (q.type === "mcq") {
      if (q.options.length < 2) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["options"], message: "Add at least 2 options." });
      }
      if (q.correctIndex >= q.options.length) {
        ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["correctIndex"], message: "Mark the correct option." });
      }
    }
    if (q.type === "true_false" && q.correctIndex > 1) {
      ctx.addIssue({ code: z.ZodIssueCode.custom, path: ["correctIndex"], message: "Choose True or False." });
    }
  });

export const quizFormSchema = z
  .object({
    title: z.string().trim().min(1, "Title is required.").max(255, "At most 255 characters."),
    description: z.string().trim().max(10_000, "At most 10000 characters."),
    minutes: z
      .string()
      .trim()
      .refine(
        (v) => v === "" || (/^\d+$/.test(v) && Number(v) >= 1 && Number(v) <= 600),
        "Enter whole minutes from 1 to 600, or leave empty.",
      ),
    due: z
      .string()
      .refine((v) => !v || !Number.isNaN(new Date(v).getTime()), "Enter a valid date and time."),
    allowRetake: z.boolean(),
    publish: z.boolean(),
    questions: z.array(questionSchema).max(MAX_QUESTIONS, `At most ${MAX_QUESTIONS} questions.`),
  })
  .superRefine((quiz, ctx) => {
    if (quiz.publish && quiz.questions.length === 0) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["questions"],
        message: "Add at least one question before publishing.",
      });
    }
    const total = quiz.questions.reduce((sum, q) => sum + (Number(q.points) || 0), 0);
    if (total > MAX_TOTAL_POINTS) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["questions"],
        message: `The total points must not exceed ${MAX_TOTAL_POINTS}.`,
      });
    }
  });

/**
 * Declared by hand: with `strictNullChecks` off, zod's `z.infer` marks every key optional.
 * The schema above is still the single source of validation.
 */
export interface QuestionFormValues {
  type: QuestionType;
  prompt: string;
  points: string;
  correctIndex: number;
  options: { text: string }[];
}

export interface QuizFormValues {
  title: string;
  description: string;
  minutes: string;
  due: string;
  allowRetake: boolean;
  publish: boolean;
  questions: QuestionFormValues[];
}

export function newQuestion(type: QuestionType = "mcq"): QuestionFormValues {
  return {
    type,
    prompt: "",
    points: "1",
    correctIndex: 0,
    options:
      type === "true_false"
        ? [{ text: "True" }, { text: "False" }]
        : type === "mcq"
          ? [{ text: "" }, { text: "" }]
          : [],
  };
}

/** Form values -> API payload. Runs only on valid values. */
export function toPayload(values: QuizFormValues): QuizCreatePayload {
  const payload: QuizCreatePayload = {
    title: values.title,
    allow_retake: values.allowRetake,
    published: values.publish,
    questions: values.questions.map((q) => ({
      prompt: q.prompt,
      type: q.type,
      points: Number(q.points),
      options:
        q.type === "short_answer"
          ? q.options.map((o) => ({ text: o.text, is_correct: true })) // accepted answers
          : q.type === "true_false"
            ? [
                { text: "True", is_correct: q.correctIndex === 0 },
                { text: "False", is_correct: q.correctIndex === 1 },
              ]
            : q.options.map((o, i) => ({ text: o.text, is_correct: i === q.correctIndex })),
    })),
  };
  if (values.description) payload.description = values.description;
  if (values.minutes) payload.time_limit_minutes = Number(values.minutes);
  const dueAt = toIsoFromLocalInput(values.due);
  if (dueAt) payload.due_at = dueAt;
  return payload;
}
