import { Skeleton } from "@/components/ui/skeleton";

/** Shown while a lazily loaded route chunk is fetched. */
export function RouteFallback() {
  return (
    <div className="min-h-screen space-y-4 bg-background p-6" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-10 w-56" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-28 w-full" />
        ))}
      </div>
      <Skeleton className="h-72 w-full" />
    </div>
  );
}
