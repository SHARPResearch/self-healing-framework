import { Construction } from "lucide-react";

export function ComingSoonPage({ title }: { title: string }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 py-24 text-center">
      <Construction className="size-8 text-muted-foreground" />
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="max-w-sm text-sm text-muted-foreground">
        This page is not built yet -- navigation is wired up so the app shell is
        fully explorable, but only the Dashboard has real content right now.
      </p>
    </div>
  );
}
