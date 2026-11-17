import { Outlet } from "react-router-dom";

import { TopNav } from "@/components/layout/TopNav";
import { useNotificationSocket } from "@/features/notifications/useNotificationSocket";

export function AppLayout() {
  useNotificationSocket(); // one live notifications socket per signed-in tab

  return (
    <div className="min-h-screen bg-background">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-md focus:bg-primary focus:px-4 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <TopNav />
      <main id="main-content" tabIndex={-1} className="mx-auto w-full max-w-6xl px-4 py-6 focus:outline-none">
        <Outlet />
      </main>
    </div>
  );
}
