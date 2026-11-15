import { ArrowLeft, BookOpenCheck, MessageSquare, Users, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { cn } from "@/lib/utils";
import type { Classroom } from "@/types";

interface Item {
  suffix: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const ITEMS: Item[] = [
  { suffix: "", label: "Stream", icon: MessageSquare, end: true },
  { suffix: "/classwork", label: "Classwork", icon: BookOpenCheck },
  { suffix: "/people", label: "People", icon: Users },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

export function ClassroomSidebar({ classroom }: { classroom: Classroom }) {
  const base = `/classes/${classroom.id}`;
  return (
    <aside className="md:w-56 md:shrink-0">
      <Link
        to="/classes"
        className="mb-3 inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        All classes
      </Link>

      <h2 className="text-lg font-semibold leading-tight">{classroom.name}</h2>
      {classroom.section || classroom.subject ? (
        <p className="text-sm text-muted-foreground">
          {[classroom.section, classroom.subject].filter(Boolean).join(" · ")}
        </p>
      ) : null}
      {classroom.is_archived ? <p className="mt-1 text-sm font-medium text-destructive">Archived (read-only)</p> : null}

      <nav aria-label="Classroom" className="mt-3 flex gap-1 overflow-x-auto md:flex-col">
        {ITEMS.map(({ suffix, label, icon: Icon, end }) => (
          <NavLink key={label} to={`${base}${suffix}`} end={end} className={linkClass}>
            <Icon className="h-4 w-4" aria-hidden="true" />
            {label}
          </NavLink>
        ))}
      </nav>

      {classroom.my_role === "teacher" && classroom.join_code ? (
        <div className="mt-4 rounded-md border p-3 text-sm">
          <p className="text-muted-foreground">Join code</p>
          <code className="text-base font-semibold tracking-widest">{classroom.join_code}</code>
        </div>
      ) : null}
    </aside>
  );
}
