import { GraduationCap, Home, ListTodo, LogOut, Shield, User as UserIcon, type LucideIcon } from "lucide-react";
import { Link, NavLink } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { NotificationBell } from "@/features/notifications/components/NotificationBell";
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
    "group flex items-center gap-2 whitespace-nowrap rounded-full px-3.5 py-2 text-sm font-medium transition-[color,background-color,box-shadow,transform] duration-150 active:scale-[0.97] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
    isActive
      ? "bg-primary text-primary-foreground shadow-sm shadow-primary/25"
      : "text-muted-foreground hover:bg-accent hover:text-foreground",
  );

function initials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function TopNav() {
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);
  const items = user?.role === "admin" ? [...NAV_ITEMS, { to: "/admin", label: "Admin", icon: Shield }] : NAV_ITEMS;

  return (
    <header className="sticky top-0 z-40 border-b bg-background/80 backdrop-blur-md supports-[backdrop-filter]:bg-background/60">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2.5">
        <Link
          to="/"
          className="group flex items-center gap-2 rounded-lg text-lg font-bold tracking-tight focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        >
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand text-primary-foreground shadow-sm transition-transform duration-200 group-hover:-rotate-6 group-hover:scale-105">
            <GraduationCap className="h-5 w-5" aria-hidden="true" />
          </span>
          <span>
            Noor <span className="text-brand">LMS</span>
          </span>
        </Link>

        <nav aria-label="Main" className="order-last flex w-full gap-1 overflow-x-auto md:order-none md:w-auto">
          {items.map(({ to, label, icon: Icon, end }) => (
            <NavLink key={to} to={to} end={end} className={linkClass}>
              <Icon className="h-4 w-4" aria-hidden="true" />
              {label}
            </NavLink>
          ))}
        </nav>

        <div className="ml-auto flex items-center gap-2 sm:gap-3">
          <NotificationBell />
          {user ? (
            <span className="hidden items-center gap-2 sm:flex">
              <span
                className="grid h-8 w-8 place-items-center rounded-full bg-secondary text-xs font-semibold uppercase"
                aria-hidden="true"
              >
                {initials(user.full_name)}
              </span>
              <span className="text-sm">
                {user.full_name} <span className="text-muted-foreground">({user.role})</span>
              </span>
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
