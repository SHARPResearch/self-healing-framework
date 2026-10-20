import {
  Activity,
  AlertTriangle,
  Bell,
  Bot,
  GitBranch,
  GitCompareArrows,
  ScrollText,
  LayoutDashboard,
  ListTree,
  Server,
  Settings,
  Sliders,
  Zap,
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
    ],
  },
  {
    label: "Decision Engine",
    items: [
      { label: "Dependency graph", to: "/dependency-graph", icon: GitBranch },
      { to: "/anomalies", label: "Anomalies", icon: AlertTriangle },
      { label: "Decisions", to: "/decisions", icon: Zap },
      { label: "Rules", to: "/rules", icon: Sliders },
    ],
  },
  {
    label: "Operations",
    items: [
      { label: "Incidents", to: "/incidents", icon: Activity },
      { label: "Logs", to: "/logs", icon: ScrollText },
      { label: "Notifications", to: "/notifications", icon: Bell },
      { label: "Models", to: "/models", icon: ListTree },
      {
        label: "Model lifecycle",
        to: "/model-lifecycle",
        icon: GitCompareArrows,
      },
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
