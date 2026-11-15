import { Navigate, Outlet, useLocation, type Location } from "react-router-dom";

import { Spinner } from "@/components/common/Spinner";
import { useAuthStore } from "@/store/auth";

/** Login / register pages: signed-in users are sent back to where they came from. */
export function GuestRoute() {
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const location = useLocation();

  if (!hydrated) return <Spinner fullPage label="Loading…" />;
  if (user) {
    const from = (location.state as { from?: Location } | null)?.from;
    const target = from ? `${from.pathname}${from.search}${from.hash}` : "/";
    return <Navigate to={target} replace />;
  }
  return <Outlet />;
}
