export default function Home() {
  return (
    <main className="mx-auto max-w-2xl px-4 py-12 sm:px-8 sm:py-20">
      <p className="mb-3 text-sm font-semibold text-muted">SentinelAI · Local development</p>
      <h1 className="mb-4 text-3xl font-semibold tracking-tight">Local foundation</h1>
      <p className="mb-8 text-muted">
        This development page provides access to the API health checks.
        Transaction processing and account access are not available in this phase.
      </p>
      <section aria-labelledby="health-heading" className="rounded-md border border-border bg-surface p-5 sm:p-6">
        <h2 id="health-heading" className="mb-3 text-lg font-semibold">API health checks</h2>
        <p className="mb-4 text-muted">
          Each link requests the current API status and opens its JSON response.
        </p>
        <ul className="space-y-2">
          <li>
            <a className="inline-flex min-h-11 items-center rounded-md text-link underline underline-offset-4" href="/api/v1/health/live">
              Check API liveness
            </a>
          </li>
          <li>
            <a className="inline-flex min-h-11 items-center rounded-md text-link underline underline-offset-4" href="/api/v1/health/ready">
              Check dependency readiness
            </a>
          </li>
        </ul>
      </section>
      <p className="mt-6 text-sm text-muted">For local development with synthetic data only.</p>
    </main>
  );
}
