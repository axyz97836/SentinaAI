import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";

export function Button({ className = "", ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button className={`button ${className}`} {...props} />;
}

export function Field({ label, error, id, ...props }: InputHTMLAttributes<HTMLInputElement> & { label: string; error?: string }) {
  return <div className="field">
    <label htmlFor={id}>{label}</label>
    <input id={id} aria-invalid={Boolean(error)} aria-describedby={error ? `${id}-error` : undefined} {...props} />
    {error && <p id={`${id}-error`} className="field-error">{error}</p>}
  </div>;
}

export function Status({ children, error = false }: { children: ReactNode; error?: boolean }) {
  return <p className={`status ${error ? "status-error" : ""}`} role={error ? "alert" : "status"}>{children}</p>;
}

export function Footer() {
  return <footer className="footer"><span>© {new Date().getFullYear()} SentinelAI · Synthetic data only</span>
    <nav aria-label="Legal"><a href="/privacy">Privacy draft</a><a href="/terms">Terms draft</a></nav>
  </footer>;
}

export function PageHeading({ eyebrow, title, children }: { eyebrow: string; title: string; children?: ReactNode }) {
  return <header className="page-heading"><p className="eyebrow">{eyebrow}</p><h1>{title}</h1>{children}</header>;
}
