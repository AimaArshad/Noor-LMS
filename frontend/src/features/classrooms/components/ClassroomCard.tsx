import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Classroom } from "@/types";

export function ClassroomCard({ classroom }: { classroom: Classroom }) {
  const details = [classroom.section, classroom.subject].filter(Boolean).join(" · ");
  return (
    <Link
      to={`/classes/${classroom.id}`}
      className="group block h-full rounded-xl focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
    >
      <Card className="relative h-full overflow-hidden transition-[transform,box-shadow,border-color] duration-200 group-hover:-translate-y-0.5 group-hover:border-primary/30 group-hover:shadow-lg">
        <div
          aria-hidden="true"
          className="absolute inset-x-0 top-0 h-1.5 bg-brand opacity-60 transition-opacity duration-200 group-hover:opacity-100"
        />
        <CardHeader className="flex-row items-start justify-between gap-3">
          <div className="min-w-0">
            <CardTitle className="text-lg transition-colors group-hover:text-primary">
              {classroom.name}
            </CardTitle>
            <CardDescription>{details || "No details"}</CardDescription>
          </div>
          <span
            aria-hidden="true"
            className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-secondary text-muted-foreground transition-[transform,background-color,color] duration-200 group-hover:translate-x-0.5 group-hover:bg-primary group-hover:text-primary-foreground"
          >
            <ArrowRight className="h-4 w-4" />
          </span>
        </CardHeader>
        <CardContent className="flex flex-wrap items-center gap-2 text-xs">
          <span className="rounded-full bg-secondary px-2 py-0.5 font-medium capitalize">{classroom.my_role}</span>
          {classroom.is_archived ? (
            <span className="rounded-full bg-destructive/10 px-2 py-0.5 font-medium text-destructive">Archived</span>
          ) : null}
          {classroom.join_code ? (
            <span className="ml-auto text-muted-foreground">
              Code <code className="font-semibold tracking-widest text-foreground">{classroom.join_code}</code>
            </span>
          ) : null}
        </CardContent>
      </Card>
    </Link>
  );
}
