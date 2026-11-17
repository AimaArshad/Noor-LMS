import { describe, expect, it } from "vitest";

import { groupTodos } from "@/features/todo/grouping";
import type { TodoItem } from "@/types";

// Local-time constructors keep these tests independent of the machine's time zone.
const NOW = new Date(2026, 9, 11, 10, 0, 0); // Sun 11 Oct 2026, 10:00

function item(id: string, due: Date | null, done = false): TodoItem {
  return {
    id,
    user_id: "u1",
    title: id,
    due_at: due ? due.toISOString() : null,
    ref_type: "assignment",
    ref_id: id,
    is_done: done,
    created_at: NOW.toISOString(),
    classroom_id: null,
    classroom_name: null,
    link: null,
    is_overdue: false,
  };
}

const ids = (groups: ReturnType<typeof groupTodos>, key: string) =>
  groups.find((g) => g.key === key)?.items.map((i) => i.id);

describe("groupTodos", () => {
  it("splits items into overdue / today / this week / later / done", () => {
    const groups = groupTodos(
      [
        item("past-today", new Date(2026, 9, 11, 9, 0)),
        item("tonight", new Date(2026, 9, 11, 18, 0)),
        item("tomorrow", new Date(2026, 9, 12, 8, 0)),
        item("day-6", new Date(2026, 9, 17, 23, 0)),
        item("day-7", new Date(2026, 9, 18, 0, 0)),
        item("no-date", null),
        item("finished", new Date(2026, 9, 1), true),
      ],
      NOW,
    );

    expect(groups.map((g) => g.key)).toEqual(["overdue", "today", "week", "later", "done"]);
    expect(ids(groups, "overdue")).toEqual(["past-today"]);
    expect(ids(groups, "today")).toEqual(["tonight"]);
    expect(ids(groups, "week")).toEqual(["tomorrow", "day-6"]);
    expect(ids(groups, "later")).toEqual(["day-7", "no-date"]); // undated items come last
    expect(ids(groups, "done")).toEqual(["finished"]);
  });

  it("sorts each group by due date, then title", () => {
    const groups = groupTodos(
      [
        item("b", new Date(2026, 9, 5)),
        item("a", new Date(2026, 9, 5)),
        item("older", new Date(2026, 9, 1)),
      ],
      NOW,
    );
    expect(ids(groups, "overdue")).toEqual(["older", "a", "b"]);
  });

  it("returns every group, even when empty", () => {
    const groups = groupTodos([], NOW);
    expect(groups).toHaveLength(5);
    expect(groups.every((g) => g.items.length === 0)).toBe(true);
  });
});
