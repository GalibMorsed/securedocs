import { Navigate, Outlet, useLocation } from "react-router-dom";
import type { ReactNode } from "react";
import { useAuth } from "./AuthProvider";

function AuthLoading() {
  return (
    <main className="grid min-h-screen place-items-center px-6">
      <p className="text-sm text-muted" role="status">
        Checking your session…
      </p>
    </main>
  );
}

export function RequireAuth() {
  const { state } = useAuth();
  const location = useLocation();

  if (state === "loading") return <AuthLoading />;
  if (state === "anonymous") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <Outlet />;
}

export function GuestOnly({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();
  if (state === "loading") return <AuthLoading />;
  if (state === "authenticated") {
    const requestedPath = (location.state as { from?: unknown } | null)?.from;
    const destination =
      typeof requestedPath === "string" &&
      requestedPath.startsWith("/") &&
      !requestedPath.startsWith("//")
        ? requestedPath
        : "/dashboard";
    return <Navigate to={destination} replace />;
  }
  return children;
}

export function HomeRedirect() {
  const { state } = useAuth();
  if (state === "loading") return <AuthLoading />;
  return <Navigate to={state === "authenticated" ? "/dashboard" : "/login"} replace />;
}
