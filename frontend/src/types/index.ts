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
