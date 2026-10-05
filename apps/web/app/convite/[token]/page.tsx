import type { Metadata } from "next";
import { AuthAside } from "@/components/AuthAside";
import { AcceptInvite } from "./AcceptInvite";

export const metadata: Metadata = { title: "Aceitar convite", robots: { index: false, follow: false } };

export default async function InvitePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = await params;
  return <div className="auth">
    <AuthAside/>
    <main className="auth-main" id="conteudo"><AcceptInvite token={token}/></main>
  </div>;
}
