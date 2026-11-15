import { Link } from "react-router-dom";

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import type { Classroom } from "@/types";

export function ClassroomCard({ classroom }: { classroom: Classroom }) {
  const details = [classroom.section, classroom.subject].filter(Boolean).join(" · ");
  return (
    <Link
      to={`/classes/${classroom.id}`}
      className="block h-full rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <Card className="h-full transition-colors hover:bg-accent/50">
        <CardHeader>
          <CardTitle className="text-lg">{classroom.name}</CardTitle>
          <CardDescription>{details || "No details"}</CardDescription>
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
