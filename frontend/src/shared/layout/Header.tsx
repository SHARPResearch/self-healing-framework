import { Building2, Check, ChevronsUpDown, LayoutDashboard, LogOut, Plus, Settings, User } from "lucide-react";
import { Link } from "react-router-dom";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { NotificationPanel } from "@/features/notifications/components/NotificationPanel";
import { LiveStatusBadge } from "@/shared/components/LiveStatusBadge";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Separator } from "@/components/ui/separator";
import { AUTH_ENABLED, authClient, logOut, switchOrganization, useSession } from "@/lib/auth";

const initials = (name: string) =>
  name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]?.toUpperCase()).join("") || "?";

export function Header({ pageTitle }: { pageTitle: string }) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-border px-6">
      <div className="flex items-center gap-2 text-sm">
        <LayoutDashboard className="size-4 text-muted-foreground" />
        <span className="font-medium">{pageTitle}</span>
      </div>

      <div className="flex items-center gap-3">
        {AUTH_ENABLED && <OrganizationSwitcher />}
        <LiveStatusBadge />
        <NotificationPanel />

        <Separator orientation="vertical" className="h-6" />

        {AUTH_ENABLED ? <UserMenu /> : <LocalUserMenu />}
      </div>
    </header>
  );
}

/** The active organization (the tenant every page shows) and a way to switch or create one. */
function OrganizationSwitcher() {
  const { data: session } = useSession();
  const { data: orgs } = authClient.useListOrganizations();
  const activeId = session?.session.activeOrganizationId;
  const active = orgs?.find((o) => o.id === activeId);
  return (
    <DropdownMenu>
      <DropdownMenuTrigger className="flex items-center gap-2 rounded-md border border-border/60 px-2.5 py-1.5 text-xs outline-none hover:bg-muted/50 focus-visible:ring-2 focus-visible:ring-ring">
        <Building2 className="size-3.5 text-muted-foreground" />
        <span className="max-w-40 truncate font-medium">{active?.name ?? "Organization"}</span>
        <ChevronsUpDown className="size-3.5 text-muted-foreground" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel className="text-xs text-muted-foreground">Organizations</DropdownMenuLabel>
        {(orgs ?? []).map((o) => (
          <DropdownMenuItem key={o.id} onSelect={() => o.id !== activeId && void switchOrganization(o.id)}>
            <span className="flex-1 truncate">{o.name}</span>
            {o.id === activeId && <Check className="size-4" />}
          </DropdownMenuItem>
        ))}
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/organization">
            <Settings className="mr-2 size-4" />
            Members and invitations
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/onboarding">
            <Plus className="mr-2 size-4" />
            New organization
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

function UserMenu() {
  const { data: session } = useSession();
  const name = session?.user.name ?? "";
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Open user menu"
        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <Avatar className="size-8">
          <AvatarFallback>{initials(name)}</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-56">
        <DropdownMenuLabel>
          <span className="block truncate">{name}</span>
          <span className="block truncate text-xs font-normal text-muted-foreground">{session?.user.email}</span>
        </DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/profile">
            <User className="mr-2 size-4" />
            Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/settings">
            <Settings className="mr-2 size-4" />
            Settings
          </Link>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => void logOut()}>
          <LogOut className="mr-2 size-4" />
          Log out
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

/** Accounts off (the local demo build): the menu as it was, with no real user. */
function LocalUserMenu() {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger aria-label="Open user menu"
        className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring">
        <Avatar className="size-8">
          <AvatarFallback>SH</AvatarFallback>
        </Avatar>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-48">
        <DropdownMenuLabel>Local demo</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem asChild>
          <Link to="/profile">
            <User className="mr-2 size-4" />
            Profile
          </Link>
        </DropdownMenuItem>
        <DropdownMenuItem asChild>
          <Link to="/settings">
            <Settings className="mr-2 size-4" />
            Settings
          </Link>
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
