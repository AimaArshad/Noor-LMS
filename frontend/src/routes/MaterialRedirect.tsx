import { Navigate, useParams } from "react-router-dom";

/**
 * Notifications link to `/classes/{id}/materials/{materialId}`, but materials are listed on the
 * Classwork tab (there is no per-material page). Send the reader there instead of a 404.
 */
export function MaterialRedirect() {
  const { classroomId = "" } = useParams();
  return <Navigate to={`/classes/${classroomId}/classwork`} replace />;
}
