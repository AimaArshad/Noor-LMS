import { Navigate, Outlet } from "react-router-dom";

import { ForbiddenPage } from "@/pages/ForbiddenPage";
import { useAuthStore } from "@/store/auth";
import type { UserRole } from "@/types";

interface RoleRouteProps {
  /** Global platform roles allowed to see the child routes. */
  roles: UserRole[];
}

/**
 * Restricts child routes to some global roles. Nest it INSIDE `ProtectedRoute`.
 * This is a UX guard only; the API enforces the real permissions.
 */
export function RoleRoute({ roles }: RoleRouteProps) {
  const user = useAuthStore((s) => s.user);
  if (!user) return <Navigate to="/login" replace />;
  return roles.includes(user.role) ? <Outlet /> : <ForbiddenPage />;
}
