import { CreateClassroomDialog } from "@/features/classrooms/components/CreateClassroomDialog";
import { JoinClassroomDialog } from "@/features/classrooms/components/JoinClassroomDialog";
import { useAuthStore } from "@/store/auth";

/** "Join class" for everyone, "Create class" for teachers and admins. */
export function ClassroomActions() {
  const role = useAuthStore((s) => s.user?.role);
  const canCreate = role === "teacher" || role === "admin";
  return (
    <div className="flex flex-wrap gap-2">
      <JoinClassroomDialog />
      {canCreate ? <CreateClassroomDialog /> : null}
    </div>
  );
}
