import { ServiceRow } from "../components/ServiceRow";
import { useReadiness } from "../hooks/useReadiness";

export function StatusPage() {
  const { data, error, loading, refresh } = useReadiness();

  const summary = error
    ? "The API is not reachable"
    : loading && !data
      ? "Checking services"
      : data?.status === "ok"
        ? "All services are connected"
        : "Some services are unreachable";

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col justify-center px-6 py-16">
      <h1 className="text-4xl font-semibold tracking-tight">SecureDocs</h1>
      <p className="mt-2 text-muted">
        Secure document management with AI search. This page checks that your
        local environment is ready.
      </p>

      <section
        aria-labelledby="env-heading"
        className="mt-10 rounded-lg border border-line bg-surface px-6"
      >
        <div className="flex items-center justify-between border-b border-line py-4">
          <h2 id="env-heading" className="font-semibold" role="status">
            {summary}
          </h2>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="rounded-md bg-accent px-3.5 py-1.5 text-sm font-medium text-white hover:brightness-110 disabled:opacity-60"
          >
            {loading ? "Checking" : "Check again"}
          </button>
        </div>

        {error && (
          <p className="py-4 text-sm text-fail" role="alert">
            {error}
          </p>
        )}

        {data && (
          <ul className="divide-y divide-line">
            {data.services.map((s) => (
              <ServiceRow key={s.name} service={s} />
            ))}
          </ul>
        )}
      </section>

      {data && (
        <p className="mt-4 text-sm text-muted">
          API v{data.version}, {data.environment} environment
        </p>
      )}
    </main>
  );
}
