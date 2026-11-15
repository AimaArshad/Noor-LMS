import { GraduationCap, Home, ListTodo, LogOut, Shield, User as UserIcon, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/store/auth";

interface NavItem {
  to: string;
  label: string;
  icon: LucideIcon;
  end?: boolean;
}

const NAV_ITEMS: NavItem[] = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/todo", label: "To-Do", icon: ListTodo },
  { to: "/classes", label: "Classes", icon: GraduationCap },
  { to: "/profile", label: "Profile", icon: UserIcon },
];

const linkClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "flex items-center gap-2 whitespace-nowrap rounded-md px-3 py-2 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive ? "bg-primary/10 text-primary" : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

export function TopNav() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const items = user?.role === "admin" ? [...NAV_ITEMS, { to: "/admin", label: "Admin", icon: Shield }] : NAV_ITEMS;

  return (
    <header className="border-b bg-background">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2">
        <Link to="/" className="text-lg font-bold tracking-tight">
          Noor LMS
        </Link>

        <nav aria-label="Main" className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          {user ? (
            <span className="hidden text-sm sm:inline">
              {user.full_name} <span className="text-muted-foreground">({user.role})</span>
            </span>
          ) : null}
          <Button variant="outline" size="sm" onClick={() => void logout()}>
            <LogOut aria-hidden="true" />
            Log out
          </Button>
        </div>
      </div>
    </header>
  );
}
