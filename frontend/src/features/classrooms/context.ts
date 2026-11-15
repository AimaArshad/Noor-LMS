import { useOutletContext } from "react-router-dom";

import type { Classroom } from "@/types";

/** The classroom loaded by `ClassroomLayout`, for its child pages. */
export function useClassroomContext(): { classroom: Classroom } {
  return useOutletContext<{ classroom: Classroom }>();
}
