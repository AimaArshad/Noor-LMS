import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { Spinner } from "@/components/common/Spinner";
import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useClassrooms } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function ClassesPage() {
  useDocumentTitle("Classes");
  const { data, isPending, error } = useClassrooms();

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Classes
      </h1>

      {isPending ? <Spinner label="Loading your classes…" /> : null}
      {error ? (
        <p role="alert" className="mt-4 text-destructive">
          {getErrorMessage(error)}
        </p>
      ) : null}

      {data && data.length === 0 ? (
        <p className="mt-4 text-muted-foreground">
          You are not in any class yet. Creating and joining classes comes in the next step.
        </p>
      ) : null}

      {data && data.length > 0 ? (
        <ul className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {data.map((classroom) => (
            <li key={classroom.id}>
              <Link
                to={`/classes/${classroom.id}`}
                className="block rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Card className="h-full transition-colors hover:bg-accent/50">
                  <CardHeader>
                    <CardTitle className="text-lg">{classroom.name}</CardTitle>
                    <CardDescription>
                      {[classroom.section, classroom.subject].filter(Boolean).join(" · ") || "No details"}
                    </CardDescription>
                    <p className="text-xs uppercase tracking-wide text-muted-foreground">
                      {classroom.my_role}
                      {classroom.is_archived ? " · archived" : ""}
                    </p>
                  </CardHeader>
                </Card>
              </Link>
            </li>
          ))}
        </ul>
      ) : null}
    </section>
  );
}
