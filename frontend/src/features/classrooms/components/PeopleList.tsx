import { useAuthStore } from "@/store/auth";
import type { ClassroomMember } from "@/types";

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function PeopleList({ title, members }: { title: string; members: ClassroomMember[] }) {
  const myId = useAuthStore((s) => s.user?.id);
  const headingId = `people-${title.toLowerCase()}`;
  return (
    <section aria-labelledby={headingId}>
      <h2 id={headingId} className="border-b pb-2 text-lg font-semibold">
        {title} <span className="text-sm font-normal text-muted-foreground">({members.length})</span>
      </h2>
      {members.length === 0 ? (
        <p className="py-4 text-sm text-muted-foreground">Nobody here yet.</p>
      ) : (
        <ul className="divide-y">
          {members.map((member) => (
            <li key={member.user.id} className="flex items-center gap-3 py-3">
              <span
                aria-hidden="true"
                className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-sm font-semibold text-primary"
              >
                {initials(member.user.full_name)}
              </span>
              <span className="min-w-0 break-words font-medium">
                {member.user.full_name}
                {member.user.id === myId ? <span className="font-normal text-muted-foreground"> (you)</span> : null}
              </span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
