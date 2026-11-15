import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useDocumentTitle } from "@/hooks/useDocumentTitle";
import { useAuthStore } from "@/store/auth";

export function ProfilePage() {
  useDocumentTitle("Profile");
  const user = useAuthStore((s) => s.user);
  if (!user) return null; // ProtectedRoute guarantees a user

  const rows: [string, string][] = [
    ["Name", user.full_name],
    ["Email", user.email],
    ["Role", user.role],
    ["Member since", new Date(user.created_at).toLocaleDateString()],
  ];

  return (
    <section aria-labelledby="page-title" className="max-w-xl">
      <h1 id="page-title" className="text-2xl font-semibold tracking-tight">
        Profile
      </h1>
      <Card className="mt-6">
        <CardHeader>
          <CardTitle className="text-lg">Your account</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[8rem_1fr] gap-y-3 text-sm">
            {rows.map(([term, value]) => (
              <div key={term} className="contents">
                <dt className="text-muted-foreground">{term}</dt>
                <dd className="break-words font-medium">{value}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-4 text-sm text-muted-foreground">Editing your profile is not available yet.</p>
        </CardContent>
      </Card>
    </section>
  );
}
