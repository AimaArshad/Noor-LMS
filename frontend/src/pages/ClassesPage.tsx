import { useState } from "react";

import { ClassroomActions } from "@/features/classrooms/components/ClassroomActions";
import { ClassroomsOverview } from "@/features/classrooms/components/ClassroomsOverview";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassesPage() {
  useDocumentTitle("Classes");
  const [includeArchived, setIncludeArchived] = useState(false);

  return (
    <section aria-labelledby="page-title">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
          Classes
        </h1>
        <ClassroomActions />
      </div>

      <label className="mb-4 mt-4 flex w-fit items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={includeArchived}
          onChange={(e) => setIncludeArchived(e.target.checked)}
          className="h-4 w-4 accent-primary"
        />
        Show archived classes
      </label>

      <ClassroomsOverview includeArchived={includeArchived} />
    </section>
  );
}
