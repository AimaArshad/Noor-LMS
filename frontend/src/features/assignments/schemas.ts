import { z } from "zod";

import type { AttachmentRef } from "@/types";

export const attachmentSchema = z.object({
  file_id: z.string().uuid(),
  name: z.string(),
  mime_type: z.string().nullish(),
});

const validDate = (value: string) => !value || !Number.isNaN(new Date(value).getTime());

export const assignmentFormSchema = z.object({
  title: z.string().trim().min(1, "Title is required.").max(255, "At most 255 characters."),
  description: z.string().trim().max(10_000, "At most 10000 characters."),
  due: z.string().refine(validDate, "Enter a valid date and time."),
  points: z
    .string()
    .trim()
    .regex(/^\d+$/, "Enter a whole number.")
    .refine((v) => Number(v) >= 1 && Number(v) <= 100_000, "Enter a number from 1 to 100000."),
  publish: z.boolean(),
  attachments: z.array(attachmentSchema).max(20),
});
/**
 * Declared by hand: with `strictNullChecks` off (this project's tsconfig), zod's
 * `z.infer` marks every key optional. The schemas stay the single source of validation.
 */
export interface AssignmentFormValues {
  title: string;
  description: string;
  due: string;
  points: string;
  publish: boolean;
  attachments: AttachmentRef[];
}

export const submissionFormSchema = z
  .object({
    content: z.string().max(20_000, "At most 20000 characters."),
    attachments: z.array(attachmentSchema).max(20),
  })
  .refine((v) => v.content.trim().length > 0 || v.attachments.length > 0, {
    message: "Write an answer or attach at least one file.",
    path: ["content"],
  });
export interface SubmissionFormValues {
  content: string;
  attachments: AttachmentRef[];
}

/** Grade must be a number with at most 2 decimals, between 0 and the assignment's points. */
export function gradeFormSchema(maxPoints: number) {
  return z.object({
    grade: z
      .string()
      .trim()
      .regex(/^\d+(\.\d{1,2})?$/, "Enter a number (up to 2 decimals).")
      .refine((v) => Number(v) <= maxPoints, `At most ${maxPoints}.`),
    feedback: z.string().max(5_000, "At most 5000 characters."),
  });
}
export type GradeFormValues = { grade: string; feedback: string };
