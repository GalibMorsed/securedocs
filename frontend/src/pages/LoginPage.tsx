import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { AuthPageShell } from "../components/AuthPageShell";
import { PasswordInput } from "../components/PasswordInput";

interface LoginLocationState {
  from?: string;
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as LoginLocationState | null)?.from;
  const destination = from?.startsWith("/") && !from.startsWith("//") ? from : "/dashboard";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      await login(email, password);
      navigate(destination, { replace: true });
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "We could not sign you in. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageShell
      title="Welcome back"
      description="Sign in to continue to your SecureDocs workspace."
      footer={
        <>
          New to SecureDocs?{" "}
          <Link className="font-semibold text-accent hover:underline" to="/register">
            Create an account
          </Link>
        </>
      }
    >
      <form className="space-y-5" onSubmit={handleSubmit}>
        {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-fail" role="alert">{error}</p>}
        <div>
          <label htmlFor="email" className="mb-2 block text-sm font-medium">Work email</label>
          <input
            id="email"
            name="email"
            type="email"
            autoComplete="email"
            required
            maxLength={320}
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            className="w-full rounded-lg border border-line bg-white px-3.5 py-3 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-blue-100"
            placeholder="you@company.com"
          />
        </div>
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label htmlFor="password" className="block text-sm font-medium">Password</label>
          </div>
          <PasswordInput
            id="password"
            name="password"
            autoComplete="current-password"
            required
            maxLength={128}
            value={password}
            onChange={setPassword}
            placeholder="Enter your password"
          />
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:brightness-110 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-wait disabled:opacity-60"
        >
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p className="mt-6 text-center text-xs leading-5 text-muted">
        By continuing, you agree to keep your workspace credentials private.
      </p>
    </AuthPageShell>
  );
}
