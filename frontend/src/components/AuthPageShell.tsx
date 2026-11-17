import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ThemeToggle } from "./ThemeToggle";

export function AuthPageShell({
  title,
  description,
  children,
  footer,
}: {
  title: string;
  description: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <main className="relative grid min-h-screen bg-white lg:grid-cols-[minmax(0,1fr)_minmax(420px,0.9fr)]">
      <ThemeToggle className="fixed right-5 top-5 z-20" />
      <section className="relative hidden overflow-hidden bg-[#12283f] px-12 py-10 text-white lg:flex lg:flex-col lg:justify-between xl:px-20">
        <div className="absolute -right-28 top-1/4 h-96 w-96 rounded-full border border-white/10" />
        <div className="absolute -right-10 top-[32%] h-64 w-64 rounded-full border border-white/10" />
        <Link to="/login" className="relative z-10 text-lg font-semibold tracking-tight">
          SecureDocs<span className="text-cyan-300">.</span>
        </Link>
        <div className="relative z-10 max-w-xl pb-10">
          <p className="mb-5 text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">
            Your knowledge, organized
          </p>
          <h2 className="text-4xl font-semibold leading-tight xl:text-5xl">
            Find the answers hidden in your documents.
          </h2>
          <p className="mt-6 max-w-lg text-lg leading-8 text-slate-300">
            A secure workspace for your team’s files and the knowledge inside them.
          </p>
        </div>
        <p className="relative z-10 text-xs text-slate-400">SecureDocs · Private team workspace</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-6 py-12 sm:px-10">
        <div className="w-full max-w-md">
          <Link to="/login" className="mb-12 inline-block text-xl font-semibold tracking-tight lg:hidden">
            SecureDocs<span className="text-accent">.</span>
          </Link>
          <header className="mb-8">
            <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-2 text-sm leading-6 text-muted">{description}</p>
          </header>
          {children}
          <div className="mt-7 text-center text-sm text-muted">{footer}</div>
        </div>
      </section>
    </main>
  );
}
