import { NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { suffix: "", label: "Stream", end: true },
  { suffix: "/classwork", label: "Classwork", end: false },
  { suffix: "/people", label: "People", end: false },
  { suffix: "/grades", label: "Grades", end: false },
];

/** Link-based tabs: each tab is a real route, so back/forward and deep links work. */
export function ClassroomTabs({ classroomId }: { classroomId: string }) {
  const base = `/classes/${classroomId}`;
  return (
    <nav aria-label="Classroom sections" className="border-b">
      <ul className="-mb-px flex gap-1 overflow-x-auto">
        {TABS.map(({ suffix, label, end }) => (
          <li key={label}>
            <NavLink
              to={`${base}${suffix}`}
              end={end}
              className={({ isActive }) =>
                cn(
                  "block whitespace-nowrap border-b-2 px-4 py-2.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  isActive
                    ? "border-primary text-primary"
                    : "border-transparent text-muted-foreground hover:text-foreground",
                )
              }
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
