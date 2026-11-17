import { NavLink, useLocation } from "react-router-dom";

import { cn } from "@/lib/utils";

const TABS = [
  { suffix: "", label: "Stream", end: true },
  { suffix: "/classwork", label: "Classwork", end: false },
  { suffix: "/people", label: "People", end: false },
  { suffix: "/grades", label: "Grades", end: false },
];

/** Assignment and quiz pages live under the Classwork tab, so it stays highlighted there. */
const CLASSWORK_DETAIL = /\/(assignments|quizzes)(\/|$)/;

/** Link-based tabs: each tab is a real route, so back/forward and deep links work. */
export function ClassroomTabs({ classroomId }: { classroomId: string }) {
  const base = `/classes/${classroomId}`;
  const { pathname } = useLocation();
  const inClasswork = CLASSWORK_DETAIL.test(pathname);

  return (
    <nav
      aria-label="Classroom sections"
      className="w-fit max-w-full overflow-x-auto rounded-full border bg-muted/60 p-1"
    >
      <ul className="flex gap-1">
        {TABS.map(({ suffix, label, end }) => (
          <li key={label}>
            <NavLink
              to={`${base}${suffix}`}
              end={end}
              className={({ isActive }) => {
                const active = label === "Classwork" ? isActive || inClasswork : isActive;
                return cn(
                  "block whitespace-nowrap rounded-full px-4 py-2 text-sm font-medium transition-[color,background-color,box-shadow] duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  active
                    ? "bg-background text-primary shadow-sm"
                    : "text-muted-foreground hover:bg-background/70 hover:text-foreground",
                );
              }}
            >
              {label}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
