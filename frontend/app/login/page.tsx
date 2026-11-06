import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { readSession } from "../_lib/session";
import { Brand } from "../_components/brand";
import { Contours, Terrain } from "../_components/atlas-graphics";
import { LoginForm } from "../_components/login-form";
import { Footer, Status } from "../_components/ui";

export const metadata: Metadata = { title: "Sign in", description: "Sign in to the SentinelAI synthetic-data demonstration workspace." };

export default async function Login({ searchParams }: { searchParams: Promise<{ reason?: string }> }) {
  if (await readSession()) redirect("/dashboard");
  const { reason } = await searchParams;
  return <div className="login-page">
    <header className="public-header"><Brand /><span className="eyebrow header-note">Signal Atlas / Demo workspace</span></header>
    <main id="main" className="login-grid">
      <section className="login-story" aria-label="About this demonstration">
        <p className="eyebrow"><span className="index-mark">01</span> Editorial risk intelligence</p>
        <h1>See the signal.<br /><em>Trace the reason.</em></h1>
        <p className="story-copy">Explore synthetic transaction signals.<br />Keep evidence behind each decision in view.</p>
        <ul className="method-notes" aria-label="Our approach"><li>Signals in context</li><li>Evidence before conclusions</li><li>Accountable investigation</li><li>Careful interpretation</li></ul>
        <div className="login-landscape"><Contours /><Terrain /></div>
        <div className="art-caption"><span>Signal / Context / Evidence</span><span aria-hidden="true">S / A</span></div>
      </section>
      <section className="login-panel" aria-labelledby="signin-title">
        <div className="login-form-wrap"><p className="eyebrow">Your workspace</p>
          <h2 id="signin-title">Welcome back.</h2><p className="muted">Sign in to continue your work.</p>
          {reason === "expired" && <Status>Your session is no longer available. Sign in again to continue.</Status>}
          {reason === "signed-out" && <Status>You have been signed out.</Status>}
          <LoginForm />
          <div className="login-note"><span className="small-cross" aria-hidden="true">+</span><p>A demonstration using fictional transactions. Scores are screening signals, not proof of fraud.</p></div>
        </div>
      </section>
    </main>
    <Footer />
  </div>;
}
