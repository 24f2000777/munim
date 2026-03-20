import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session) redirect("/login");
  const userType = (session.user as any)?.userType ?? "smb_owner";
  return <AppShell userType={userType}>{children}</AppShell>;
}
