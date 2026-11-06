"use client";

import { useEffect, useRef, useState, type ReactNode } from "react";
import { flushSync } from "react-dom";
import { authRequest, csrfProof, roleLabels, type Identity } from "../_lib/auth";
import { Brand } from "./brand";
import { Contours, Icon } from "./atlas-graphics";
import { Button, Footer, Status } from "./ui";
import { useHydrated } from "../_lib/use-hydrated";

function Navigation({ identity }: { identity: Identity }) {
  return <><p className="eyebrow rail-label">Workspace</p>
    <nav aria-label="Workspace"><a className="nav-item" href="/dashboard" aria-current="page"><Icon name="home" /> Overview</a></nav>
    <div className="rail-context"><p className="eyebrow">Current access</p><div className="rail-identity"><Icon name="person" /><div><strong>{identity.user.display_name}</strong><p className="muted">{roleLabels[identity.role]}</p></div></div><div className="rail-organization"><strong>{identity.organization.name}</strong><p className="muted">Organization</p></div></div>
    <p className="rail-purpose">A dedicated space for transaction signals, evidence and clear reasoning. Only available pages appear here.</p>
  </>;
}

export function Workspace({ identity, children }: { identity: Identity; children: ReactNode }) {
  const hydrated = useHydrated();
  const dialog = useRef<HTMLDialogElement>(null);
  const menu = useRef<HTMLButtonElement>(null);
  const checking = useRef(false);
  const leaving = useRef(false);
  const [verified, setVerified] = useState(true);
  const [unavailable, setUnavailable] = useState(false);
  const [logoutError, setLogoutError] = useState("");
  const [busy, setBusy] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    async function check() {
      if (document.hidden || checking.current || leaving.current) return;
      checking.current = true; setMenuOpen(false); setVerified(false); setUnavailable(false);
      try {
        const response = await authRequest("me");
        if (response.status === 401) {
          window.location.replace("/login?reason=expired"); return;
        }
        if (!response.ok) throw new Error("Session unavailable");
        const current: Identity = await response.json();
        if (JSON.stringify(current) !== JSON.stringify(identity)) {
          window.location.replace("/dashboard"); return;
        }
        setVerified(true);
      } catch { setUnavailable(true); }
      finally { checking.current = false; }
    }
    const hide = () => flushSync(() => { setMenuOpen(false); setVerified(false); });
    const visibility = () => { if (document.hidden) hide(); else void check(); };
    window.addEventListener("focus", check);
    window.addEventListener("pageshow", check);
    window.addEventListener("pagehide", hide);
    document.addEventListener("visibilitychange", visibility);
    const desktop = matchMedia("(min-width: 900px)");
    const closeOnDesktop = () => { if (desktop.matches) dialog.current?.close(); };
    desktop.addEventListener("change", closeOnDesktop);
    return () => {
      window.removeEventListener("focus", check); window.removeEventListener("pageshow", check);
      window.removeEventListener("pagehide", hide); document.removeEventListener("visibilitychange", visibility);
      desktop.removeEventListener("change", closeOnDesktop);
    };
  }, [identity]);

  async function logout() {
    if (leaving.current) return;
    leaving.current = true; setBusy(true); setLogoutError("");
    try {
      const proof = await csrfProof();
      const response = await authRequest("logout", { method: "POST", headers: { "X-CSRF-Token": proof } });
      if (response.ok || response.status === 401) {
        setVerified(false);
        window.location.replace(`/login?reason=${response.ok ? "signed-out" : "expired"}`);
        return;
      }
      throw new Error("Logout failed");
    } catch {
      setLogoutError("Could not sign out. Your session may still be active. Please try again.");
      leaving.current = false; setBusy(false);
    }
  }

  if (!verified) return <div className="session-screen"><Brand /><main id="main">
    <h1>{unavailable ? "Session check unavailable" : "Checking your session…"}</h1>
    <Status error={unavailable}>{unavailable ? "Your workspace is hidden until your session can be verified." : "Connecting to your workspace."}</Status>
    {unavailable && <a className="button" href="/dashboard">Try again</a>}
  </main><Footer /></div>;

  return <div className="workspace">
    <header className="workspace-header"><Brand /><div className="header-session"><span className="eyebrow header-note">Signal Atlas / Demo workspace</span><a href="#account-heading" className="header-account"><Icon name="person" /><span><strong>{identity.user.display_name}</strong><span>{roleLabels[identity.role]}</span></span></a></div>
      <button ref={menu} disabled={!hydrated} className="button secondary mobile-toggle" aria-label="Open navigation" aria-expanded={menuOpen} aria-controls="mobile-navigation" onClick={() => { dialog.current?.showModal(); setMenuOpen(true); }}><Icon name="menu" /></button>
    </header>
    <aside className="sidebar"><Navigation identity={identity} /><div className="rail-footnote"><Contours /><p>Keep the evidence<br />in view.</p></div></aside>
    <dialog id="mobile-navigation" ref={dialog} className="mobile-drawer" aria-labelledby="navigation-title" onClose={() => { setMenuOpen(false); menu.current?.focus(); }} onKeyDown={event => {
      if (event.key !== "Tab") return;
      const controls = event.currentTarget.querySelectorAll<HTMLElement>("a[href], button:not(:disabled)");
      const first = controls[0], last = controls[controls.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
      <div className="drawer-heading"><h2 id="navigation-title">Navigation</h2><Button className="secondary" onClick={() => dialog.current?.close()}>Close</Button></div>
      <Navigation identity={identity} />
      <nav className="drawer-legal" aria-label="Navigation legal links"><a href="/privacy">Privacy draft</a><a href="/terms">Terms draft</a></nav>
    </dialog>
    <div className="workspace-body"><div className="account-bar"><span>{identity.organization.name}</span><span className="account-role">{roleLabels[identity.role]}</span></div>
      <main id="main" className="workspace-main">{children}
        <section className="account-panel" aria-labelledby="account-heading"><div className="session-identity"><span className="session-icon"><Icon name="person" /></span><div><p className="eyebrow">Your session</p><h2 id="account-heading">{identity.user.display_name}</h2><p className="muted">{roleLabels[identity.role]} · {identity.organization.name}</p></div></div><Button className="secondary" disabled={busy || !hydrated} onClick={logout}>{busy ? "Signing out…" : "Sign out"}<span aria-hidden="true">↗</span></Button>
          {logoutError && <Status error>{logoutError}</Status>}
        </section>
      </main><Footer />
    </div>
  </div>;
}
