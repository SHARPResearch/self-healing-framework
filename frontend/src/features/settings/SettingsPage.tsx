import { AppShell } from "@/shared/layout/AppShell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ToastHost } from "@/shared/components/ToastHost";
import { ThresholdsTab } from "./components/ThresholdsTab";
import { ModelTab } from "./components/ModelTab";
import { IntegrationsTab } from "./components/IntegrationsTab";
import { NotificationsTab } from "./components/NotificationsTab";
import { SecurityTab } from "./components/SecurityTab";
import { RuntimeTab } from "./components/RuntimeTab";

export function SettingsPage() {
  return (
    <AppShell pageTitle="Settings">
      <Tabs defaultValue="runtime" className="space-y-6">
        <TabsList>
          <TabsTrigger value="runtime">Runtime</TabsTrigger>
          <TabsTrigger value="thresholds">Thresholds</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>

        <TabsContent value="runtime">
          <RuntimeTab />
        </TabsContent>
        <TabsContent value="thresholds">
          <ThresholdsTab />
        </TabsContent>
        <TabsContent value="model">
          <ModelTab />
        </TabsContent>
        <TabsContent value="integrations">
          <IntegrationsTab />
        </TabsContent>
        <TabsContent value="notifications">
          <NotificationsTab />
        </TabsContent>
        <TabsContent value="security">
          <SecurityTab />
        </TabsContent>
      </Tabs>
      <ToastHost />
    </AppShell>
  );
}
