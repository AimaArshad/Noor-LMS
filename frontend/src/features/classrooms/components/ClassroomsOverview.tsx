import { getErrorMessage } from "@/api/errors";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Spinner } from "@/components/common/Spinner";
import { Button } from "@/components/ui/button";
import { ClassroomCard } from "@/features/classrooms/components/ClassroomCard";
import { useClassrooms } from "@/features/classrooms/hooks";
import { useAuthStore } from "@/store/auth";

/** The grid of the user's classrooms, with loading, error and empty states. */
export function ClassroomsOverview({ includeArchived = false }: { includeArchived?: boolean }) {
  const role = useAuthStore((s) => s.user?.role);
  const { data, isPending, isError, error, refetch, isFetching } = useClassrooms({ includeArchived });
  const classrooms = data ?? [];

  if (isPending) return <Spinner label="Loading your classes…" />;

  if (isError) {
    return (
      <div className="space-y-3">
        <ErrorAlert message={getErrorMessage(error)} />
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
          Try again
        </Button>
      </div>
    );
  }

  if (classrooms.length === 0) {
    const canCreate = role === "teacher" || role === "admin";
    return (
      <div className="rounded-lg border border-dashed p-10 text-center">
        <p className="font-medium">You are not in any class yet.</p>
        <p className="mt-1 text-sm text-muted-foreground">
          {canCreate
            ? "Create your first class, or join one with a code."
            : "Ask your teacher for a join code, then use “Join class”."}
        </p>
      </div>
    );
  }

  return (
    <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {classrooms.map((classroom) => (
        <li key={classroom.id}>
          <ClassroomCard classroom={classroom} />
        </li>
      ))}
    </ul>
  );
}
