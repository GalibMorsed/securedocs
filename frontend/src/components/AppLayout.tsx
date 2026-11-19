import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/AuthProvider";
import { ThemeToggle } from "./ThemeToggle";

export function AppLayout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  function handleLogout() {
    logout();
    navigate("/login", { replace: true });
  }

  const linkClass = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-3 py-2 text-sm font-medium transition ${isActive ? "bg-blue-50 text-accent" : "text-muted hover:bg-slate-50 hover:text-ink"}`;

  return (
    <div className="min-h-screen bg-paper">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-4 px-5 sm:px-8">
          <NavLink to="/dashboard" className="shrink-0 text-lg font-semibold tracking-tight">
            SecureDocs<span className="text-accent">.</span>
          </NavLink>
          <nav aria-label="Main navigation" className="flex items-center gap-1">
            <NavLink to="/dashboard" className={linkClass}>Overview</NavLink>
            <NavLink to="/documents" className={linkClass}>Documents</NavLink>
            <NavLink to="/search" className={linkClass}>Search</NavLink>
            <NavLink to="/chat" className={linkClass}>Chat</NavLink>
            <NavLink to="/status" className={linkClass}>System status</NavLink>
          </nav>
          <div className="flex items-center gap-3">
            <ThemeToggle />
            <span className="hidden max-w-40 truncate text-sm text-muted sm:block" title={user?.email}>
              {user?.full_name}
            </span>
            <button type="button" onClick={handleLogout} className="rounded-md border border-line px-3 py-2 text-sm font-medium hover:bg-slate-50">
              Sign out
            </button>
          </div>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
