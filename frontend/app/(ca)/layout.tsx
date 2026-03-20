import { auth } from "@/lib/auth";
import { redirect } from "next/navigation";
import { AppShell } from "@/components/layout/AppShell";

export default async function CALayout({ children }: { children: React.ReactNode }) {
  const session = await auth();
  if (!session) redirect("/login");

  const userType = (session.user as any)?.userType ?? "smb_owner";
  if (userType !== "ca_firm") redirect("/dashboard");

  return <AppShell userType="ca_firm">{children}</AppShell>;
}
