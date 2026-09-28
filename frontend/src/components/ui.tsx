import type { ReactNode } from "react";

export function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ready: "bg-accent-soft text-accent-deep",
    processing: "bg-warn-soft text-warn",
    queued: "bg-warn-soft text-warn",
    failed: "bg-danger-soft text-danger",
    empty: "bg-line-soft text-muted",
    done: "bg-accent-soft text-accent-deep",
    running: "bg-warn-soft text-warn",
  };
  return <span className={`rounded-sm px-1.5 py-0.5 font-mono text-[11px] uppercase tracking-wide ${styles[status] ?? "bg-line-soft text-muted"}`}>{status}</span>;
}

export function Panel({ title, actions, children, className = "" }: { title?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`panel ${className}`}>
      {title !== undefined && (
        <div className="panel-head">
          <span>{title}</span>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 p-4 text-[13px] text-muted">
      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-line border-t-accent-deep" />
      {label}…
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="p-6 text-center text-[13px] text-muted">{children}</div>;
}

export function ErrorNote({ error }: { error: unknown }) {
  const message = error instanceof Error ? error.message : String(error);
  return <div className="m-3 rounded-md border border-danger/30 bg-danger-soft px-3 py-2 text-[13px] text-danger">{message}</div>;
}

export function Swatch({ color }: { color: string }) {
  return <span className="inline-block h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: color }} />;
}

export function Slider({ label, value, min, max, step, onChange, format }: { label: string; value: number; min: number; max: number; step: number; onChange: (v: number) => void; format?: (v: number) => string }) {
  return (
    <label className="block">
      <span className="mb-1 flex items-center justify-between">
        <span className="label mb-0">{label}</span>
        <span className="font-mono text-[12px] text-ink-2">{format ? format(value) : value}</span>
      </span>
      <input type="range" min={min} max={max} step={step} value={value} onChange={(e) => onChange(Number(e.target.value))} />
    </label>
  );
}
