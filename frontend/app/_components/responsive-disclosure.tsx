"use client";

import { useEffect, useRef, type ReactNode } from "react";

export function ResponsiveDisclosure({ id, title, eyebrow, mobileOpen = false, className = "", children }: {
  id: string; title: string; eyebrow?: string; mobileOpen?: boolean; className?: string; children: ReactNode;
}) {
  const details = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const element = details.current;
    if (!element) return;
    const desktop = matchMedia("(min-width: 768px)");
    let remembered = mobileOpen;
    const update = () => {
      const nextOpen = desktop.matches || remembered;
      const restoreFocus = !nextOpen && element.contains(document.activeElement);
      const summary = element.querySelector("summary")!;
      element.open = nextOpen;
      summary.tabIndex = desktop.matches ? -1 : 0;
      if (restoreFocus) summary.focus();
    };
    const remember = () => { if (!desktop.matches) remembered = element.open; };
    update();
    element.addEventListener("toggle", remember);
    desktop.addEventListener("change", update);
    return () => { element.removeEventListener("toggle", remember); desktop.removeEventListener("change", update); };
  }, [mobileOpen]);
  // Keep evidence accessible even before hydration or without JavaScript.
  return <details ref={details} open className={`tx-disclosure ${className}`} id={id}>
    <summary onClick={event => { if (matchMedia("(min-width: 768px)").matches) event.preventDefault(); }}>
      <span>{eyebrow && <span className="eyebrow">{eyebrow}</span>}<h2>{title}</h2></span>
      <span className="tx-disclosure-indicator" aria-hidden="true" />
    </summary>
    <div className="tx-disclosure-content">{children}</div>
  </details>;
}
