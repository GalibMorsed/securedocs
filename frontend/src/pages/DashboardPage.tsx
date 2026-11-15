import { Link } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";

export function DashboardPage() {
  const { user } = useAuth();

  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
      <p className="text-sm font-semibold text-accent">WORKSPACE OVERVIEW</p>
      <div className="mt-2 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight sm:text-4xl">Welcome, {user?.full_name}</h1>
          <p className="mt-2 text-muted">Your secure team workspace is ready.</p>
        </div>
        <Link to="/documents" className="rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:brightness-110">
          Browse documents
        </Link>
      </div>

      <section className="mt-10 grid gap-5 md:grid-cols-2">
        <article className="rounded-xl border border-line bg-white p-6 shadow-sm">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-blue-50 text-accent" aria-hidden="true">01</div>
          <h2 className="mt-5 text-lg font-semibold">Your workspace</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            You are signed in as <span className="font-medium text-ink">{user?.email}</span>. Your account created a private organization workspace.
          </p>
        </article>
        <article className="rounded-xl border border-line bg-white p-6 shadow-sm">
          <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-ok" aria-hidden="true">02</div>
          <h2 className="mt-5 text-lg font-semibold">Document library</h2>
          <p className="mt-2 text-sm leading-6 text-muted">
            The document API is the next product area. Your protected library route is ready for uploads and search.
          </p>
          <Link to="/documents" className="mt-4 inline-flex text-sm font-semibold text-accent hover:underline">
            Open document library <span className="ml-1" aria-hidden="true">→</span>
          </Link>
        </article>
      </section>
    </main>
  );
}
