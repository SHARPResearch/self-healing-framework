import {
  Activity,
  Bell,
  Bot,
  GitBranch,
  LayoutDashboard,
  ListTree,
  Server,
  Settings,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: typeof LayoutDashboard;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

export const navGroups: NavGroup[] = [
  {
    label: "Monitor",
    items: [
      { label: "Dashboard", to: "/dashboard", icon: LayoutDashboard },
      { label: "Services", to: "/services", icon: Server },
      { label: "Dependency graph", to: "/dependency-graph", icon: GitBranch },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Incidents", to: "/incidents", icon: Activity },
      { label: "Notifications", to: "/notifications", icon: Bell },
      { label: "Models", to: "/models", icon: ListTree },
    ],
  },
  {
    label: "Assistant",
    items: [{ label: "Copilot", to: "/copilot", icon: Bot }],
  },
  {
    label: "Administration",
    items: [{ label: "Settings", to: "/settings", icon: Settings }],
  },
];
