import { AppShell } from "@/shared/layout/AppShell";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ThresholdsTab } from "./components/ThresholdsTab";
import { ModelTab } from "./components/ModelTab";
import { IntegrationsTab } from "./components/IntegrationsTab";
import { NotificationsTab } from "./components/NotificationsTab";
import { SecurityTab } from "./components/SecurityTab";

export function SettingsPage() {
  return (
    <AppShell pageTitle="Settings">
      <Tabs defaultValue="thresholds" className="space-y-6">
        <TabsList>
          <TabsTrigger value="thresholds">Thresholds</TabsTrigger>
          <TabsTrigger value="model">Model</TabsTrigger>
          <TabsTrigger value="integrations">Integrations</TabsTrigger>
          <TabsTrigger value="notifications">Notifications</TabsTrigger>
          <TabsTrigger value="security">Security</TabsTrigger>
        </TabsList>

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
    </AppShell>
  );
}
