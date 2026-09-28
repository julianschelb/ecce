import { useState, type FormEvent } from "react";
import { useAuth } from "@/hooks/useAuth";
import { ApiError } from "@/lib/api";

export function AdminModal({ onClose }: { onClose?: () => void }) {
  const { login } = useAuth();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(password);
      setPassword("");
      onClose?.();
    } catch (e) {
      if (e instanceof ApiError && e.status === 503) setError("Admin access is disabled on this server (ADMIN_PASSWORD is not set).");
      else if (e instanceof ApiError && e.status === 429) setError("Too many attempts. Please wait a minute.");
      else setError("Wrong password.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-16 max-w-sm">
      <form onSubmit={submit} className="panel p-6">
        <h2 className="text-[22px]">Administration</h2>
        <p className="mt-1 text-[13px] text-muted">Enter the admin password to manage corpora.</p>
        <label className="label mt-5" htmlFor="admin-password">
          Password
        </label>
        <input id="admin-password" className="input" type="password" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus required />
        {error && <div className="mt-2 text-[13px] text-danger">{error}</div>}
        <div className="mt-4 flex items-center justify-between">
          <span className="font-mono text-[11px] text-muted">Bearer token · 12 h</span>
          <button type="submit" className="btn btn-primary" disabled={busy || !password}>
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </div>
      </form>
    </div>
  );
}
