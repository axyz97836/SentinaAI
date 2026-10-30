import type { ReactNode } from "react";
import { Brand } from "./brand";
import { Footer, PageHeading } from "./ui";

export function LegalPage({ title, children }: { title: string; children: ReactNode }) {
  return <div className="legal-page"><header className="public-header"><Brand /><a href="/">Return to workspace</a></header><main id="main" className="legal-content"><PageHeading eyebrow="Owner-review draft / Not final policy" title={title} /><p className="draft-notice">This draft describes the local demonstration. It requires owner review before any public deployment and is not an approved legal policy.</p>{children}</main><Footer /></div>;
}
