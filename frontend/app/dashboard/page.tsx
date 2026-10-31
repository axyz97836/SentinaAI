import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { readSession } from "../_lib/session";
import { Workspace } from "../_components/workspace";
import { Contours, Terrain, Icon } from "../_components/atlas-graphics";
import { PageHeading } from "../_components/ui";

export const metadata: Metadata = { title: "Workspace overview", description: "Your authenticated SentinelAI demonstration workspace." };

export default async function Dashboard() {
  const identity = await readSession();
  if (!identity) redirect("/login?reason=expired");
  return <Workspace identity={identity}>
    <div className="workspace-intro"><PageHeading eyebrow="Workspace / 01" title="A place for clear decisions."><p className="muted">Your demonstration workspace, with evidence at its core.</p></PageHeading><div className="workspace-landscape"><Contours /><Terrain /></div></div>
    <div className="information-grid">
      <section className="information-module foundation-module" aria-labelledby="foundation-heading"><div className="module-icon"><Icon name="check" /></div><div><h2 id="foundation-heading">Foundation is ready</h2><p>You’re signed in. The application shell and authenticated session are ready for your work.</p><p className="module-footnote">Operational interfaces are not available yet.</p></div></section>
      <section className="information-module capabilities-module" aria-labelledby="capabilities-heading"><div className="module-icon"><Icon name="layers" /></div><div><h2 id="capabilities-heading">What this workspace will support</h2><ul><li>Transaction risk scoring and explanations</li><li>Alert review and case investigation</li><li>Evidence and audit history</li><li>Role-based access control</li></ul><p className="module-footnote">Backend capabilities. Frontend workflows arrive in later phases.</p></div></section>
      <section className="information-module interpretation-module" aria-labelledby="interpretation-heading"><div className="module-icon"><Icon name="book" /></div><div><h2 id="interpretation-heading">Important notes</h2><p>This is a synthetic-data demonstration. Risk scores are screening signals, not proof of fraud.</p><p className="module-footnote">The composite score is not a calibrated fraud probability.</p></div></section>
    </div>
  </Workspace>;
}
