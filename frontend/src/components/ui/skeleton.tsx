import { cn } from "@/lib/utils";

/** Shimmering placeholder used while a list loads (see `.skeleton` in index.css). */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden="true" className={cn("skeleton rounded-lg", className)} />;
}
