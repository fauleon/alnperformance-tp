import type { Metadata } from "next";
import { Suspense } from "react";
import { AuthAside } from "@/components/AuthAside";
import { LoginForm } from "./LoginForm";

export const metadata: Metadata = { title: "Entrar", robots: { index: false, follow: false } };

export default function LoginPage() {
  return <div className="auth">
    <AuthAside/>
    <main className="auth-main" id="conteudo">
      <h2>Entrar no painel</h2>
      <p className="muted">Use o e-mail e a senha do seu convite.</p>
      <Suspense><LoginForm/></Suspense>
    </main>
  </div>;
}
