import { StrictMode } from "react";
import { createRoot } from "react-dom/client";

import { App } from "@/App";
import "@/index.css";
import { useAuthStore } from "@/store/auth";

// Restore the session from localStorage. hydrate() is idempotent and shares one promise,
// so StrictMode / double calls can never trigger two refresh-token rotations.
void useAuthStore.getState().hydrate();

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
