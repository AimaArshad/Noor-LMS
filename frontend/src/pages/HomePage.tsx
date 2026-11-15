import { GraduationCap, ListTodo } from "lucide-react";
import { Link } from "react-router-dom";

import { Card, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function HomePage() {
  useDocumentTitle("Home");
  const user = useAuthStore((s) => s.user);

  return (
    <section aria-labelledby="page-title">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Welcome{user ? `, ${user.full_name}` : ""}
      </h1>
      <p className="mt-1 text-muted-foreground">Here is where your day starts.</p>

      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Link to="/classes" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Card className="h-full transition-colors hover:bg-accent/50">
            <CardHeader>
              <GraduationCap className="h-6 w-6 text-primary" aria-hidden="true" />
              <CardTitle className="text-lg">Your classes</CardTitle>
              <CardDescription>Open a class to see its stream, classwork and people.</CardDescription>
            </CardHeader>
          </Card>
        </Link>
        <Link to="/todo" className="rounded-lg focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
          <Card className="h-full transition-colors hover:bg-accent/50">
            <CardHeader>
              <ListTodo className="h-6 w-6 text-primary" aria-hidden="true" />
              <CardTitle className="text-lg">To-Do</CardTitle>
              <CardDescription>Assignments and quizzes that are waiting for you.</CardDescription>
            </CardHeader>
          </Card>
        </Link>
      </div>
    </section>
  );
}
