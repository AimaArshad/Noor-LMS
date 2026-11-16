import type { components } from "@/api/types";

// App-level names for the generated contract in `@/api/types`.
// This file is the ONLY place that maps OpenAPI schema names to app names.

export type UserRole = components["schemas"]["UserRole"];
export type MemberRole = components["schemas"]["MemberRole"];

/** Full profile (GET /auth/me). */
export type User = components["schemas"]["UserRead"];
/** Minimal profile safe to show to classmates (no email). */
export type UserPublic = components["schemas"]["UserPublic"];

export type TokenPair = components["schemas"]["TokenPair"];
export type LoginInput = components["schemas"]["LoginRequest"];

/**
 * The generated type allows `role: UserRole` because the field has a server default.
 * Self-registration can only be teacher/student, so narrow it here.
 */
export type RegisterInput = Omit<components["schemas"]["RegisterRequest"], "role"> & {
  role: Exclude<UserRole, "admin">;
};

/** Response of every classroom endpoint (GET /classrooms, /classrooms/{id}). */
export type Classroom = components["schemas"]["ClassroomDetail"];

/**
 * Body of POST /classrooms. The generated type also allows `null` for the optional text fields;
 * the form only ever has "a string" or "absent", so narrow it here.
 */
export type ClassroomCreateInput = Omit<
  components["schemas"]["ClassroomCreate"],
  "section" | "subject" | "room"
> & {
  section?: string;
  subject?: string;
  room?: string;
};
export type ClassroomMember = components["schemas"]["ClassroomMemberRead"];
export type ClassroomPeople = components["schemas"]["ClassroomPeople"];

export type Message = components["schemas"]["Message"];

/** Offset-paginated list response (the API exposes one concrete `Page_*` per resource). */
export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// --- Step 15: stream, classwork, people, grades -------------------------------------------

export type Announcement = components["schemas"]["AnnouncementRead"];

export type CommentTarget = components["schemas"]["CommentTarget"];
/** Named `CommentRecord` so it does not shadow the DOM `Comment` type. */
export type CommentRecord = components["schemas"]["CommentRead"];

export type AttachmentRef = components["schemas"]["AttachmentRef"];

export type AssignmentState = components["schemas"]["AssignmentState"];
export type Assignment = components["schemas"]["AssignmentRead"];

/**
 * Body of POST /classrooms/{id}/assignments. The generated type allows `null` for the optional
 * text fields; the form only ever has "a string" or "absent", so narrow it here.
 */
export type AssignmentCreateInput = Omit<
  components["schemas"]["AssignmentCreate"],
  "description" | "due_at"
> & {
  description?: string;
  due_at?: string;
};

export type SubmissionState = components["schemas"]["SubmissionState"];
export type Submission = components["schemas"]["SubmissionRead"];
export type SubmissionList = components["schemas"]["SubmissionList"];

export type QuizSummary = components["schemas"]["QuizSummary"];
export type QuestionType = components["schemas"]["QuestionType"];

export type QuizOptionPublic = components["schemas"]["QuizOptionPublic"];
/** Teacher view: includes the answer key. */
export type QuizOptionKey = components["schemas"]["QuizOptionRead"];

interface QuizQuestionBase {
  id: string;
  prompt: string;
  type: QuestionType;
  points: number;
  order_index: number;
}
export type StudentQuestion = QuizQuestionBase & { options: QuizOptionPublic[] };
export type TeacherQuestion = QuizQuestionBase & { quiz_id: string; options: QuizOptionKey[] };

/** `GET /quizzes/{id}` as a student: no answer key. */
export type StudentQuiz = Omit<components["schemas"]["QuizStudentRead"], "questions"> & {
  questions: StudentQuestion[];
};
/** `GET /quizzes/{id}` as a teacher: with the answer key. */
export type TeacherQuiz = Omit<components["schemas"]["QuizRead"], "questions"> & {
  questions: TeacherQuestion[];
};
export type QuizView = StudentQuiz | TeacherQuiz;

/** The generated schema marks the nullable fields optional; the API always sends them. */
export type AnswerResult = Omit<
  components["schemas"]["AnswerResult"],
  "selected_option_id" | "answer_text" | "is_correct" | "points_awarded"
> & {
  selected_option_id: string | null;
  answer_text: string | null;
  /** null = awaiting manual grading */
  is_correct: boolean | null;
  points_awarded: number | null;
};

export type AttemptResult = Omit<
  components["schemas"]["AttemptResult"],
  "student" | "submitted_at" | "expires_at" | "score" | "max_score" | "answers"
> & {
  student: UserPublic | null;
  submitted_at: string | null;
  expires_at: string | null;
  score: number | null;
  max_score: number | null;
  answers: AnswerResult[];
};

export type AttemptStart = Omit<components["schemas"]["AttemptStart"], "expires_at" | "quiz"> & {
  expires_at: string | null;
  quiz: StudentQuiz;
};

export type MyAttempt = Omit<components["schemas"]["MyAttemptRead"], "attempt"> & {
  attempt: AttemptResult | null;
};

export type QuizResults = Omit<
  components["schemas"]["QuizResults"],
  "average_score" | "attempts"
> & {
  average_score: number | null;
  attempts: AttemptResult[];
};

/** Body of POST /classrooms/{id}/quizzes; same `null` narrowing as assignments. */
export type QuizCreateInput = Omit<components["schemas"]["QuizCreate"], "description" | "due_at"> & {
  description?: string;
  due_at?: string;
};

export type QuizOptionInput = components["schemas"]["QuizOptionCreate"];
export type QuizQuestionInput = Omit<
  components["schemas"]["QuizQuestionCreate"],
  "points" | "options"
> & {
  points: number;
  options: QuizOptionInput[];
};
export type QuizCreatePayload = Omit<QuizCreateInput, "questions"> & {
  questions: QuizQuestionInput[];
};

/** Response of POST /files/upload. */
export type UploadedFile = components["schemas"]["FileRead"];

export type Material = components["schemas"]["MaterialRead"];

/** Body of POST /classrooms/{id}/materials; same `null` narrowing as assignments. */
export type MaterialCreateInput = Omit<components["schemas"]["MaterialCreate"], "description"> & {
  description?: string;
};
