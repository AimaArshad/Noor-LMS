import { ClassroomActions } from "@/features/classrooms/components/ClassroomActions";
import { ClassroomsOverview } from "@/features/classrooms/components/ClassroomsOverview";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function HomePage() {
  useDocumentTitle("Home");
  const user = useAuthStore((s) => s.user);
  const firstName = user?.full_name.split(/\s+/)[0];

  return (
    <section aria-labelledby="page-title" className="space-y-8">
      <div className="relative overflow-hidden rounded-2xl border bg-card p-6 shadow-sm sm:p-8">
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-10 -top-16 h-48 w-48 rounded-full bg-primary/10 blur-2xl"
        />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -bottom-20 right-24 h-40 w-40 rounded-full bg-[hsl(258_70%_50%/0.08)] blur-2xl"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-primary">Your learning space</p>
            <h1 id="page-title" className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">
              Welcome{firstName ? `, ${firstName}` : ""}
            </h1>
            <p className="mt-1 text-muted-foreground">Pick a class, or join or create one.</p>
          </div>
          <ClassroomActions />
        </div>
      </div>

      <div>
        <h2 className="mb-4 text-lg font-semibold">Your classes</h2>
        <ClassroomsOverview />
      </div>
    </section>
  );
}
