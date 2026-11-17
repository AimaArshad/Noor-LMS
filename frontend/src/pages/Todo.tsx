import { AlarmClock, CalendarClock, CalendarDays, CheckCircle2, ChevronDown, Inbox } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { getErrorMessage } from "@/api/errors";
import { AsyncList } from "@/components/common/AsyncList";
import { ErrorAlert } from "@/components/common/ErrorAlert";
import { Badge } from "@/components/ui/badge";
import { groupTodos, type TodoGroup } from "@/features/todo/grouping";
import { useToggleTodo, useTodos } from "@/features/todo/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { formatDateTime } from "@/lib/format";
import { cn } from "@/lib/utils";
import type { TodoItem } from "@/types";

/** Current time, refreshed every minute so items move to "Overdue" while the page is open. */
function useNow(intervalMs = 60_000): Date {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = window.setInterval(() => setNow(new Date()), intervalMs);
    return () => window.clearInterval(id);
  }, [intervalMs]);
  return now;
}

const GROUP_ICON = {
  overdue: AlarmClock,
  today: CalendarClock,
  week: CalendarDays,
  later: Inbox,
  done: CheckCircle2,
} as const;

function TodoRow({
  item,
  overdue,
  pending,
  onToggle,
}: {
  item: TodoItem;
  overdue: boolean;
  pending: boolean;
  onToggle: (isDone: boolean) => void;
}) {
  const kind = item.ref_type === "quiz" ? "Quiz" : item.ref_type === "assignment" ? "Assignment" : "Personal";
  const checkboxId = `todo-${item.id}`;
  return (
    <li className="flex items-start gap-3 px-4 py-3 transition-colors hover:bg-accent/40">
      <input
        id={checkboxId}
        type="checkbox"
        className="mt-1 h-4 w-4 shrink-0 accent-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        checked={item.is_done}
        disabled={pending}
        onChange={(e) => onToggle(e.target.checked)}
        aria-label={`Mark “${item.title}” as ${item.is_done ? "not done" : "done"}`}
      />
      <div className="min-w-0 flex-1">
        <p className={item.is_done ? "break-words text-muted-foreground line-through" : "break-words font-medium"}>
          {item.link ? (
            <Link
              to={item.link}
              className="transition-colors underline-offset-4 hover:text-primary hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {item.title}
            </Link>
          ) : (
            item.title
          )}
        </p>
        <p className="text-sm text-muted-foreground">
          {kind}
          {item.classroom_name ? ` · ${item.classroom_name}` : ""}
          {item.due_at ? (
            <>
              {" · due "}
              <time dateTime={item.due_at}>{formatDateTime(item.due_at)}</time>
            </>
          ) : (
            " · no due date"
          )}
        </p>
      </div>
      {overdue ? <Badge variant="destructive">Overdue</Badge> : null}
    </li>
  );
}

function GroupSection({
  group,
  pendingId,
  onToggle,
}: {
  group: TodoGroup;
  pendingId: string | null;
  onToggle: (item: TodoItem, isDone: boolean) => void;
}) {
  const headingId = `todo-group-${group.key}`;
  const Icon = GROUP_ICON[group.key];
  const [doneOpen, setDoneOpen] = useState(false);
  const rows = (
    <ul className="divide-y rounded-xl border bg-card shadow-sm">
      {group.items.map((item) => (
        <TodoRow
          key={item.id}
          item={item}
          overdue={group.key === "overdue"}
          pending={pendingId === item.id}
          onToggle={(isDone) => onToggle(item, isDone)}
        />
      ))}
    </ul>
  );

  const title = (
    <>
      {group.label} <span className="text-sm font-normal text-muted-foreground">({group.items.length})</span>
      {group.hint ? <span className="ml-2 text-xs font-normal text-muted-foreground">{group.hint}</span> : null}
    </>
  );

  // "Done" is collapsed by default: a native <details> is keyboard and screen-reader friendly.
  if (group.key === "done") {
    return (
      <details
        className="rounded-xl border border-dashed bg-card/60"
        open={doneOpen}
        onToggle={(event) => setDoneOpen(event.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-lg font-semibold [&::-webkit-details-marker]:hidden">
          <CheckCircle2
            className={cn("h-5 w-5 text-muted-foreground", doneOpen && "text-primary")}
            aria-hidden="true"
          />
          {title}
          <ChevronDown
            className={cn("ml-auto h-4 w-4 text-muted-foreground transition-transform", doneOpen && "rotate-180")}
            aria-hidden="true"
          />
        </summary>
        <div className="border-t">
          <ul className="divide-y">
            {group.items.map((item) => (
              <TodoRow
                key={item.id}
                item={item}
                overdue={false}
                pending={pendingId === item.id}
                onToggle={(isDone) => onToggle(item, isDone)}
              />
            ))}
          </ul>
        </div>
      </details>
    );
  }

  return (
    <section aria-labelledby={headingId} className="space-y-3">
      <h2
        id={headingId}
        className={
          group.key === "overdue"
            ? "flex items-center gap-2 text-lg font-semibold text-destructive"
            : "flex items-center gap-2 text-lg font-semibold"
        }
      >
        <Icon className="h-5 w-5" aria-hidden="true" />
        {title}
      </h2>
      {rows}
    </section>
  );
}

export function TodoPage() {
  useDocumentTitle("To-Do");
  const { data, isPending, error, refetch } = useTodos();
  const toggle = useToggleTodo();
  const now = useNow();
  const [announcement, setAnnouncement] = useState("");

  const groups = useMemo(() => (data ? groupTodos(data.items, now) : []), [data, now]);
  const pendingId = toggle.isPending ? (toggle.variables?.id ?? null) : null;

  function onToggle(item: TodoItem, isDone: boolean) {
    toggle.mutate(
      { id: item.id, isDone },
      {
        onSuccess: (updated) => {
          if (!isDone && updated.is_done) {
            setAnnouncement(`“${updated.title}” is already turned in, so it stays done.`);
          } else {
            setAnnouncement(`“${updated.title}” marked ${updated.is_done ? "done" : "not done"}.`);
          }
        },
      },
    );
  }

  return (
    <section aria-labelledby="page-title" className="mx-auto max-w-3xl space-y-6">
      <div className="relative overflow-hidden rounded-2xl border bg-card p-6 shadow-sm">
        <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1.5 bg-brand" />
        <div
          aria-hidden="true"
          className="pointer-events-none absolute -right-12 -top-16 h-40 w-40 rounded-full bg-primary/10 blur-2xl"
        />
        <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
          To-Do
        </h1>
        {data ? (
          <p className="mt-1 text-muted-foreground">
            <span className="font-medium text-foreground">{data.pending_count}</span> to do
            {data.overdue_count > 0 ? (
              <span className="text-destructive"> · {data.overdue_count} overdue</span>
            ) : null}
          </p>
        ) : (
          <p className="mt-1 text-muted-foreground">Your assignments and quizzes, soonest first.</p>
        )}
      </div>

      <ErrorAlert message={toggle.isError ? getErrorMessage(toggle.error) : null} />

      <p role="status" className="sr-only">
        {announcement}
      </p>

      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        isEmpty={data?.items.length === 0}
        emptyText="Nothing to do. Published assignments and quizzes from your classes will appear here."
        loadingLabel="Loading your to-do list…"
      >
        <div className="space-y-8">
          {groups
            .filter((group) => group.items.length > 0)
            .map((group) => (
              <GroupSection key={group.key} group={group} pendingId={pendingId} onToggle={onToggle} />
            ))}
          {data && data.total > data.items.length ? (
            <p className="text-xs text-muted-foreground">
              Showing the first {data.items.length} of {data.total} items.
            </p>
          ) : null}
        </div>
      </AsyncList>
    </section>
  );
}
