import { Link, Outlet, useLocation, useParams } from "react-router-dom";

import { getStatus } from "@/api/errors";
import { Announcer } from "@/components/common/Announcer";
import { Spinner } from "@/components/common/Spinner";
import { ClassroomHeader } from "@/features/classrooms/components/ClassroomHeader";
import { ClassroomTabs } from "@/features/classrooms/components/ClassroomTabs";
import { useClassroom } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

/** Header + tabs for every /classes/:classroomId/* page. Loads the classroom once. */
export function ClassroomLayout() {
  const { classroomId = "" } = useParams();
  const location = useLocation();
  const { data: classroom, isPending, error } = useClassroom(classroomId);
  useDocumentTitle(classroom?.name);
  // Set by the create / join dialogs: the result of the action that brought the user here.
  const announcement = (location.state as { announcement?: string } | null)?.announcement;

  if (isPending) return <Spinner label="Loading class…" />;

  if (error || !classroom) {
    const missing = getStatus(error) === 404 || getStatus(error) === 422;
    return (
      <div role="alert" className="py-10 text-center">
        <h1 className="text-xl font-semibold">{missing ? "Class not found" : "Could not load this class"}</h1>
        <p className="mt-1 text-muted-foreground">
          {missing ? "It does not exist, or you are not a member." : "Please try again in a moment."}
        </p>
        <Link to="/classes" className="mt-4 inline-block text-primary underline underline-offset-4">
          Back to your classes
        </Link>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <Announcer message={announcement} />
      <ClassroomHeader classroom={classroom} />
      <ClassroomTabs classroomId={classroom.id} />
      <div key={location.pathname} className="animate-enter">
        <Outlet context={{ classroom }} />
      </div>
    </div>
  );
}
