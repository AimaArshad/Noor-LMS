import { authHttp } from "@/api/base";
import type { LoginInput, RegisterInput, TokenPair, User } from "@/types";

export const authApi = {
  login: (body: LoginInput) =>
    authHttp.post<TokenPair>("/auth/login", body).then((r) => r.data),

  register: (body: RegisterInput) =>
    authHttp.post<User>("/auth/register", body).then((r) => r.data),

  /** Rotates tokens: the submitted refresh token can never be used again. */
  refresh: (refreshToken: string) =>
    authHttp.post<TokenPair>("/auth/refresh", { refresh_token: refreshToken }).then((r) => r.data),

  logout: (refreshToken: string) =>
    authHttp.post("/auth/logout", { refresh_token: refreshToken }).then(() => undefined),

  /** Takes the token explicitly so it can be used before the store holds it. */
  me: (accessToken: string) =>
    authHttp
      .get<User>("/auth/me", { headers: { Authorization: `Bearer ${accessToken}` } })
      .then((r) => r.data),
};
