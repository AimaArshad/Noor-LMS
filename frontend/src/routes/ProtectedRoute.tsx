import { Navigate, Outlet, useLocation } from "react-router-dom";

import { Spinner } from "@/components/common/Spinner";
import { useAuthStore } from "@/store/auth";

/** Renders its child routes only for a signed-in user. */
export function ProtectedRoute() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!hydrated) return <Spinner fullPage label="Loading your account…" />;
  if (!user) return <Navigate to="/login" replace state={{ from: location }} />;
  return <Outlet />;
}
