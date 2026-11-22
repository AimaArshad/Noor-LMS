import { AudiobooksSection } from "@/features/audiobooks/components/AudiobooksSection";
import { useClassroomContext } from "@/features/classrooms/context";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";

export function AudiobooksPage() {
  const { classroom } = useClassroomContext();
  useDocumentTitle(`${classroom.name} · Audiobooks`);

  return <AudiobooksSection classroom={classroom} />;
}

