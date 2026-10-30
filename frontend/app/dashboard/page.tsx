import type { Metadata } from "next";
import { redirect } from "next/navigation";
import { readSession } from "../_lib/session";
import { Workspace } from "../_components/workspace";
import { Mark } from "../_components/brand";
import { PageHeading } from "../_components/ui";

export const metadata: Metadata = { title: "Workspace overview", description: "Your authenticated SentinelAI demonstration workspace." };

export default async function Dashboard() {
  const identity = await readSession();
  if (!identity) redirect("/login?reason=expired");
  return <Workspace identity={identity}>
    <PageHeading eyebrow="Workspace / 01" title="A place for clear decisions."><p className="muted">Your demonstration workspace, with evidence at its core.</p></PageHeading>
    <section className="empty-state" aria-labelledby="workspace-heading"><div className="empty-mark"><Mark /></div>
      <div><p className="eyebrow">The foundation is ready</p><h2 id="workspace-heading">Signed in. Ready for what comes next.</h2>
        <p>This space will bring your transaction signals and investigation evidence together. The operational screens are not available yet.</p>
        <p className="empty-note">No activity totals are shown here. This is not a report on your organization’s data.</p>
      </div>
    </section>
    <section className="workspace-principle" aria-labelledby="principle-heading"><p className="eyebrow">A note on interpretation</p><h2 id="principle-heading">A signal invites a closer look.<br /><em>It does not tell the whole story.</em></h2><p>SentinelAI is a demonstration using fictional transactions. A risk score is a screening signal, not proof of fraud or a calibrated fraud probability.</p></section>
  </Workspace>;
}
