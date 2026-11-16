import { Navigate, useParams } from "react-router-dom";

/** `/classrooms/:id/...` is an alias of `/classes/:id/...`. */
export function ClassroomsRedirect() {
  const { classroomId = "", "*": rest } = useParams();
  return <Navigate to={`/classes/${classroomId}${rest ? `/${rest}` : ""}`} replace />;
}
