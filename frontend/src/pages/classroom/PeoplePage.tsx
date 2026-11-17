import { AsyncList } from "@/components/common/AsyncList";
import { useClassroomContext } from "@/features/classrooms/context";
import { PeopleList } from "@/features/classrooms/components/PeopleList";
import { useClassroomPeople } from "@/features/classrooms/hooks";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function PeoplePage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · People`);
  const { data, isPending, error, refetch } = useClassroomPeople(classroom.id);

  return (
    <div className="mx-auto max-w-3xl space-y-8">
      <AsyncList
        isPending={isPending}
        error={error}
        onRetry={() => void refetch()}
        loadingLabel="Loading people…"
      >
        <PeopleList title="Teachers" members={data?.teachers ?? []} />
        <PeopleList title="Students" members={data?.students ?? []} total={data?.students_total} />
      </AsyncList>
    </div>
  );
}
