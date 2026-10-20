import type { ReactNode } from "react";
import { TooltipProvider } from "@/components/ui/tooltip";
import { useUiStore } from "@/shared/store/uiStore";
import { useLiveConnection } from "@/hooks/useLiveConnection";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";

interface AppShellProps {
  pageTitle: string;
  children: ReactNode;
}

export function AppShell({ pageTitle, children }: AppShellProps) {
  const collapsed = useUiStore((state) => state.sidebarCollapsed);
  const toggleSidebar = useUiStore((state) => state.toggleSidebar);
  useLiveConnection();

  return (
    <TooltipProvider>
      <div className="flex h-screen overflow-hidden bg-background text-foreground">
        <Sidebar collapsed={collapsed} onToggle={toggleSidebar} />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header pageTitle={pageTitle} />
          <main className="scrollbar-hidden flex-1 overflow-y-auto px-6 py-6">{children}</main>
        </div>
      </div>
    </TooltipProvider>
  );
}
