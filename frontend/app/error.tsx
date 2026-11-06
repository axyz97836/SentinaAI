"use client";

import { Brand } from "./_components/brand";
import { Button, Footer } from "./_components/ui";

export default function ErrorPage({ reset }: { reset: () => void }) {
  return <div className="session-screen"><Brand /><main id="main"><p className="eyebrow">Connection interrupted</p><h1>We could not open this page.</h1><p>Your workspace has not been displayed. Check your connection and try again.</p><Button onClick={reset}>Try again</Button> <a href="/">Return home</a></main><Footer /></div>;
}
