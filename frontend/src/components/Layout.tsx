import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "@/hooks/useAuth";

export function Layout() {
  const { isAdmin } = useAuth();
  const link = ({ isActive }: { isActive: boolean }) =>
    `rounded-md px-2.5 py-1 text-[13px] font-medium transition-colors ${isActive ? "bg-pop-soft text-ink" : "text-ink-2 hover:bg-line-soft hover:text-ink"}`;
  return (
    <div className="flex min-h-screen flex-col">
      <header className="border-b border-line bg-gradient-to-b from-bg to-[#f2f1ec]">
        <div className="mx-auto flex h-12 max-w-[1600px] items-center justify-between px-4">
          <NavLink to="/" className="flex items-baseline gap-2">
            <span className="font-serif text-[19px] font-semibold tracking-tight text-ink">ECCE</span>
            <span className="hidden font-mono text-[11px] uppercase tracking-wider text-muted sm:inline">Entity-centric corpus exploration</span>
          </NavLink>
          <nav className="flex items-center gap-1">
            <NavLink to="/" end className={link}>
              Gallery
            </NavLink>
            <a href="/api/docs" className="rounded-md px-2.5 py-1 text-[13px] font-medium text-ink-2 hover:bg-line-soft hover:text-ink" target="_blank" rel="noreferrer">
              API
            </a>
            <NavLink to="/admin" className={link} title="Administration">
              {isAdmin ? "Admin ●" : "Admin"}
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="flex-1">
        <Outlet />
      </main>
      <footer className="border-t border-line-soft py-3 text-center font-mono text-[11px] text-muted">
        Implicit entity networks after Spitz &amp; Gertz · built with implicit-word-network · MIT
      </footer>
    </div>
  );
}
