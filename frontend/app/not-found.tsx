import { Brand } from "./_components/brand";
import { Footer, PageHeading } from "./_components/ui";
export default function NotFound() {
  return <div className="session-screen"><Brand /><main id="main"><PageHeading eyebrow="404 / Outside the atlas" title="This page is off the map." /><p>The address may be incorrect, or this page is not available yet.</p><a className="button" href="/">Return to workspace <span aria-hidden="true">↗</span></a></main><Footer /></div>;
}
