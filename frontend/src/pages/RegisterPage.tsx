import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthProvider";
import { AuthPageShell } from "../components/AuthPageShell";
import { PasswordInput } from "../components/PasswordInput";

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [organizationName, setOrganizationName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== confirmPassword) {
      setError("The passwords do not match.");
      return;
    }
    if (password.length < 12) {
      setError("Use at least 12 characters for your password.");
      return;
    }

    setSubmitting(true);
    try {
      await register({ email, password, full_name: fullName, organization_name: organizationName });
      navigate("/dashboard", { replace: true });
    } catch (cause) {
      setError(
        cause instanceof ApiError
          ? cause.message
          : "We could not create your account. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthPageShell
      title="Create your workspace"
      description="Set up your team and start building a private knowledge base."
      footer={
        <>
          Already have an account?{" "}
          <Link className="font-semibold text-accent hover:underline" to="/login">
            Sign in
          </Link>
        </>
      }
    >
      <form className="space-y-4" onSubmit={handleSubmit}>
        {error && <p className="rounded-lg bg-red-50 px-4 py-3 text-sm text-fail" role="alert">{error}</p>}
        <div>
          <label htmlFor="full-name" className="mb-2 block text-sm font-medium">Your name</label>
          <input id="full-name" name="name" autoComplete="name" required maxLength={255} value={fullName} onChange={(event) => setFullName(event.target.value)} className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-blue-100" placeholder="Alex Morgan" />
        </div>
        <div>
          <label htmlFor="organization" className="mb-2 block text-sm font-medium">Organization</label>
          <input id="organization" name="organization" autoComplete="organization" required minLength={2} maxLength={255} value={organizationName} onChange={(event) => setOrganizationName(event.target.value)} className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-blue-100" placeholder="Acme Inc." />
        </div>
        <div>
          <label htmlFor="register-email" className="mb-2 block text-sm font-medium">Work email</label>
          <input id="register-email" name="email" type="email" autoComplete="email" required maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} className="w-full rounded-lg border border-line px-3.5 py-3 text-sm outline-none transition focus:border-accent focus:ring-4 focus:ring-blue-100" placeholder="you@company.com" />
        </div>
        <div>
          <label htmlFor="register-password" className="mb-2 block text-sm font-medium">Password</label>
          <PasswordInput id="register-password" name="new-password" autoComplete="new-password" required minLength={12} maxLength={128} value={password} onChange={setPassword} placeholder="At least 12 characters" />
        </div>
        <div>
          <label htmlFor="confirm-password" className="mb-2 block text-sm font-medium">Confirm password</label>
          <PasswordInput id="confirm-password" name="confirm-password" autoComplete="new-password" required minLength={12} maxLength={128} value={confirmPassword} onChange={setConfirmPassword} placeholder="Enter your password again" />
        </div>
        <button type="submit" disabled={submitting} className="w-full rounded-lg bg-accent px-4 py-3 text-sm font-semibold text-white shadow-sm transition hover:brightness-110 focus-visible:ring-4 focus-visible:ring-blue-200 disabled:cursor-wait disabled:opacity-60">
          {submitting ? "Creating workspace…" : "Create account"}
        </button>
      </form>
      <p className="mt-4 text-center text-xs leading-5 text-muted">Your password is securely hashed and never stored as plain text.</p>
    </AuthPageShell>
  );
}
