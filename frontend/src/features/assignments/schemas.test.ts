import { describe, expect, it } from "vitest";

import { gradeFormSchema, submissionFormSchema } from "@/features/assignments/schemas";

describe("gradeFormSchema", () => {
  const schema = gradeFormSchema(50);

  it("accepts numbers from 0 to max_points with up to 2 decimals", () => {
    expect(schema.safeParse({ grade: "0", feedback: "" }).success).toBe(true);
    expect(schema.safeParse({ grade: "45.5", feedback: "" }).success).toBe(true);
    expect(schema.safeParse({ grade: "50", feedback: "" }).success).toBe(true);
  });

  it("rejects grades above the maximum, negatives, text and too many decimals", () => {
    for (const grade of ["51", "-1", "abc", "", "1.234"]) {
      expect(schema.safeParse({ grade, feedback: "" }).success, grade).toBe(false);
    }
  });
});

describe("submissionFormSchema", () => {
  it("needs an answer or at least one attachment", () => {
    expect(submissionFormSchema.safeParse({ content: "   ", attachments: [] }).success).toBe(false);
    expect(submissionFormSchema.safeParse({ content: "My answer", attachments: [] }).success).toBe(true);
    const file = { file_id: "6f9619ff-8b86-4011-b42d-00c04fc964ff", name: "a.pdf", mime_type: "application/pdf" };
    expect(submissionFormSchema.safeParse({ content: "", attachments: [file] }).success).toBe(true);
  });
});
