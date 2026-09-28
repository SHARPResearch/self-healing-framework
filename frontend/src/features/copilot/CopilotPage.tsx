import { AppShell } from "@/shared/layout/AppShell";
import { CopilotChat } from "./components/CopilotChat";

export function CopilotPage() {
  return (
    <AppShell pageTitle="Copilot">
      <CopilotChat />
    </AppShell>
  );
}
