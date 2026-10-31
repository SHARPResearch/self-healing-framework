import { NavLink } from "react-router-dom";
import { PanelLeft } from "lucide-react";
import { cn } from "@/lib/utils";
import { Logo } from "@/shared/components/Logo";
import { ORG_NAME, REPO_NAME } from "@/shared/brand";
import { navGroups } from "./navigation";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
}

export function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside
      className={cn(
        "flex h-screen shrink-0 flex-col border-r border-border bg-card transition-[width]",
        collapsed ? "w-[68px]" : "w-64",
      )}
    >
      <div
        className={cn(
          "flex items-center px-4 py-4",
          collapsed ? "flex-col gap-3" : "justify-between",
        )}
      >
        <Logo variant={collapsed ? "mark" : "full"} size="sm" />
        <button
          type="button"
          onClick={onToggle}
          className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          aria-label="Toggle sidebar"
        >
          <PanelLeft className="size-4" />
        </button>
      </div>

      <nav className="scrollbar-hidden flex-1 overflow-y-auto px-2">
        {navGroups.map((group) => (
          <div key={group.label} className="mb-4">
            {!collapsed && (
              <p className="mb-1 px-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {group.label}
              </p>
            )}
            <ul className="space-y-0.5">
              {group.items.map((item) => (
                <li key={item.to}>
                  <NavLink
                    to={item.to}
                    className={({ isActive }) =>
                      cn(
                        "flex items-center gap-2.5 rounded-md px-2.5 py-1.5 text-sm transition-colors",
                        isActive
                          ? "bg-secondary font-medium text-secondary-foreground"
                          : "text-muted-foreground hover:bg-accent hover:text-accent-foreground",
                      )
                    }
                    title={collapsed ? item.label : undefined}
                  >
                    <item.icon className="size-4 shrink-0" />
                    {!collapsed && <span>{item.label}</span>}
                  </NavLink>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>

      {!collapsed && (
        <div className="border-t border-border p-3 text-xs text-muted-foreground">
          <p>{REPO_NAME}</p>
          <p className="mt-0.5">{ORG_NAME}</p>
        </div>
      )}
    </aside>
  );
}
