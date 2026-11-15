import { ClassroomActions } from "@/features/classrooms/components/ClassroomActions";
import { ClassroomsOverview } from "@/features/classrooms/components/ClassroomsOverview";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function HomePage() {
  useDocumentTitle("Home");
  const user = useAuthStore((s) => s.user);

  return (
    <section aria-labelledby="page-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
            Welcome{user ? `, ${user.full_name}` : ""}
          </h1>
          <p className="mt-1 text-muted-foreground">Pick a class, or join or create one.</p>
        </div>
        <ClassroomActions />
      </div>

      <h2 className="mb-4 mt-8 text-lg font-semibold">Your classes</h2>
      <ClassroomsOverview />
    </section>
  );
}
