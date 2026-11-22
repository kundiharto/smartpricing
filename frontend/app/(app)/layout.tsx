import { AppShell } from "@/components/app-shell";
import { OrgProvider } from "@/lib/org";

export default function AppLayout({ children }: { children: React.ReactNode }) {
  return (
    <OrgProvider>
      <AppShell>{children}</AppShell>
    </OrgProvider>
  );
}
