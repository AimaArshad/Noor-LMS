import { describe, expect, it } from "vitest";

import { newQuestion, quizFormSchema, toPayload, type QuizFormValues } from "@/features/quizzes/schemas";

const base: QuizFormValues = {
  title: "Quiz 1",
  description: "",
  minutes: "",
  due: "",
  allowRetake: false,
  publish: false,
  questions: [],
};

const mcq = (overrides: Partial<QuizFormValues["questions"][number]> = {}): QuizFormValues["questions"][number] => ({
  type: "mcq",
  prompt: "2+2?",
  points: "2",
  correctIndex: 1,
  options: [{ text: "3" }, { text: "4" }],
  ...overrides,
});

describe("quizFormSchema", () => {
  it("accepts a valid multiple-choice quiz", () => {
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq()] }).success).toBe(true);
  });

  it("rejects duplicate options (case-insensitive) and too few options", () => {
    const duplicates = quizFormSchema.safeParse({
      ...base,
      questions: [mcq({ options: [{ text: "A" }, { text: "a" }] })],
    });
    expect(duplicates.success).toBe(false);

    const tooFew = quizFormSchema.safeParse({ ...base, questions: [mcq({ options: [{ text: "only" }] })] });
    expect(tooFew.success).toBe(false);
  });

  it("requires questions when publishing and positive points", () => {
    expect(quizFormSchema.safeParse({ ...base, publish: true }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq({ points: "0" })] }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, questions: [mcq({ points: "1.234" })] }).success).toBe(false);
  });

  it("rejects an invalid time limit", () => {
    expect(quizFormSchema.safeParse({ ...base, minutes: "0" }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, minutes: "601" }).success).toBe(false);
    expect(quizFormSchema.safeParse({ ...base, minutes: "30" }).success).toBe(true);
  });
});

describe("toPayload", () => {
  it("marks exactly the chosen multiple-choice option as correct", () => {
    const payload = toPayload({ ...base, minutes: "20", questions: [mcq()] });
    expect(payload.time_limit_minutes).toBe(20);
    expect(payload.questions[0]).toMatchObject({
      type: "mcq",
      points: 2,
      options: [
        { text: "3", is_correct: false },
        { text: "4", is_correct: true },
      ],
    });
  });

  it("builds fixed True/False options", () => {
    const tf = { ...newQuestion("true_false"), prompt: "Sky is blue", correctIndex: 1 };
    expect(toPayload({ ...base, questions: [tf] }).questions[0]?.options).toEqual([
      { text: "True", is_correct: false },
      { text: "False", is_correct: true },
    ]);
  });

  it("treats short-answer options as accepted answers and omits empty optional fields", () => {
    const short = { ...newQuestion("short_answer"), prompt: "Capital?", options: [{ text: "Paris" }] };
    const payload = toPayload({ ...base, questions: [short] });
    expect(payload.questions[0]?.options).toEqual([{ text: "Paris", is_correct: true }]);
    expect(payload).not.toHaveProperty("description");
    expect(payload).not.toHaveProperty("time_limit_minutes");
    expect(payload).not.toHaveProperty("due_at");
  });
});
