import { Link } from "react-router-dom";

export function DocumentsPage() {
  return (
    <main className="mx-auto max-w-7xl px-5 py-10 sm:px-8 sm:py-14">
      <p className="text-sm font-semibold text-accent">LIBRARY</p>
      <h1 className="mt-2 text-3xl font-semibold tracking-tight">Documents</h1>
      <p className="mt-2 max-w-2xl text-muted">Your team’s files and searchable knowledge will live here.</p>

      <section className="mt-8 rounded-xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center sm:px-12">
        <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-blue-50 text-accent" aria-hidden="true">◇</div>
        <h2 className="mt-5 text-lg font-semibold">Your library is ready for its first document</h2>
        <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-muted">
          Uploads and document management are not enabled yet. The protected page and account flow are in place; document APIs are the next implementation step.
        </p>
        <Link to="/dashboard" className="mt-6 inline-flex rounded-lg border border-line px-4 py-2.5 text-sm font-semibold hover:bg-slate-50">
          Back to overview
        </Link>
      </section>
    </main>
  );
}
