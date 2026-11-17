import type { TodoItem } from "@/types";

export type TodoGroupKey = "overdue" | "today" | "week" | "later" | "done";

export interface TodoGroup {
  key: TodoGroupKey;
  label: string;
  hint?: string;
  items: TodoItem[];
}

const startOfDay = (d: Date) => new Date(d.getFullYear(), d.getMonth(), d.getDate());

function addDays(date: Date, days: number): Date {
  const next = new Date(date);
  next.setDate(next.getDate() + days); // calendar arithmetic: safe across DST changes
  return next;
}

const FAR = Number.MAX_SAFE_INTEGER;
const dueTime = (item: TodoItem) => (item.due_at ? new Date(item.due_at).getTime() : FAR);

/**
 * Split items into Overdue / Today / This week / Later / Done (in the user's local time).
 *
 * * Overdue: not done and due before `now`.
 * * Today:   due from `now` until the end of today.
 * * This week: due tomorrow through the next 6 days.
 * * Later:   due after that, or no due date.
 * * Done:    everything finished (any date).
 *
 * Every group is returned (possibly empty) in a fixed order; items are sorted by due date.
 */
export function groupTodos(items: TodoItem[], now: Date = new Date()): TodoGroup[] {
  const tomorrow = addDays(startOfDay(now), 1);
  const weekEnd = addDays(startOfDay(now), 7);

  const groups: Record<TodoGroupKey, TodoItem[]> = { overdue: [], today: [], week: [], later: [], done: [] };

  for (const item of items) {
    if (item.is_done) {
      groups.done.push(item);
    } else if (!item.due_at) {
      groups.later.push(item);
    } else {
      const due = new Date(item.due_at);
      if (due < now) groups.overdue.push(item);
      else if (due < tomorrow) groups.today.push(item);
      else if (due < weekEnd) groups.week.push(item);
      else groups.later.push(item);
    }
  }

  for (const list of Object.values(groups)) {
    list.sort((a, b) => dueTime(a) - dueTime(b) || a.title.localeCompare(b.title));
  }

  return [
    { key: "overdue", label: "Overdue", items: groups.overdue },
    { key: "today", label: "Today", items: groups.today },
    { key: "week", label: "This week", hint: "Next 7 days", items: groups.week },
    { key: "later", label: "Later", hint: "Including items with no due date", items: groups.later },
    { key: "done", label: "Done", items: groups.done },
  ];
}
