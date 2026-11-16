import { useClassroomContext } from "@/features/classrooms/context";
import { StudentGrades } from "@/features/grades/components/StudentGrades";
import { TeacherGrades } from "@/features/grades/components/TeacherGrades";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function GradesPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Grades`);

  return classroom.my_role === "teacher" ? (
    <TeacherGrades classroomId={classroom.id} />
  ) : (
    <div className="space-y-3">
      <h2 className="text-xl font-semibold">Your grades</h2>
      <p className="text-sm text-muted-foreground">Scores for assignments appear after your teacher returns your work.</p>
      <StudentGrades classroomId={classroom.id} />
    </div>
  );
}
