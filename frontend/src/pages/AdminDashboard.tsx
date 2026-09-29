import { useState } from "react";
import { Link } from "react-router-dom";
import { AdminModal } from "@/components/AdminModal";
import { JobProgress, PasteCorpusForm, UploadCorpusForm } from "@/components/AdminForms";
import { Empty, ErrorNote, Panel, Spinner, StatusBadge } from "@/components/ui";
import { useAdminMutations, useCorpora, useHealth, useJobs } from "@/hooks/useApi";
import { useAuth } from "@/hooks/useAuth";
import { useDocumentMeta } from "@/hooks/useDocumentMeta";
import { formatDate, formatNumber } from "@/lib/format";

export function AdminDashboard() {
  const { isAdmin, checking, logout } = useAuth();
  useDocumentMeta({ title: "Administration · ECCE", noindex: true });
  if (checking) return <Spinner label="Checking session" />;
  if (!isAdmin) return <AdminModal />;
  return <Dashboard onLogout={logout} />;
}

function Dashboard({ onLogout }: { onLogout: () => void }) {
  const corpora = useCorpora(true);
  const jobs = useJobs(true);
  const health = useHealth();
  const { processCorpus, updateCorpus, deleteCorpus } = useAdminMutations();
  const [tab, setTab] = useState<"paste" | "upload">("paste");
  const [notice, setNotice] = useState<string | null>(null);

  const busy = processCorpus.isPending || updateCorpus.isPending || deleteCorpus.isPending;
  const mutationError = processCorpus.error ?? updateCorpus.error ?? deleteCorpus.error;

  return (
    <div className="mx-auto max-w-[1400px] px-4 py-6">
      <div className="mb-5 flex items-center justify-between">
        <div>
          <h1 className="text-[28px]">Administration</h1>
          <div className="meta">
            extractor: {health.data?.extractor ?? "…"} · full-text index: {health.data?.fts ? "FTS5" : "fallback"} · API v{health.data?.version}
          </div>
        </div>
        <button type="button" className="btn" onClick={onLogout}>
          Sign out
        </button>
      </div>
      {notice && <div className="mb-4 rounded-md border border-accent/40 bg-accent-soft px-3 py-2 text-[13px] text-accent-deep">{notice}</div>}
      {mutationError && <ErrorNote error={mutationError} />}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[1fr_440px]">
        <Panel title={`Corpora · ${corpora.data?.length ?? 0}`}>
          {corpora.isLoading && <Spinner />}
          {corpora.data && corpora.data.length === 0 && <Empty>No corpora yet.</Empty>}
          {corpora.data && corpora.data.length > 0 && (
            <table className="w-full text-[13px]">
              <thead className="text-left font-mono text-[11px] uppercase tracking-wider text-muted">
                <tr className="border-b border-line-soft">
                  <th className="px-4 py-2">Corpus</th>
                  <th className="px-2 py-2">Status</th>
                  <th className="px-2 py-2 text-right">Docs</th>
                  <th className="px-2 py-2 text-right">Entities</th>
                  <th className="px-2 py-2 text-right">Edges</th>
                  <th className="px-2 py-2">Updated</th>
                  <th className="px-4 py-2 text-right">Actions</th>
                </tr>
              </thead>
              <tbody>
                {corpora.data.map((c) => (
                  <tr key={c.slug} className="border-b border-line-soft align-top">
                    <td className="px-4 py-2">
                      <div className="font-medium">
                        {c.status === "ready" ? <Link to={`/corpus/${c.slug}`} className="hover:text-accent-deep">{c.title}</Link> : c.title}
                        {!c.visible && <span className="ml-2 chip">hidden</span>}
                      </div>
                      <div className="meta">{c.author ? `${c.author} · ` : ""}{c.slug}{c.genre ? ` · ${c.genre}` : ""}</div>
                      {c.error && <div className="mt-1 text-[12px] text-danger">{c.error}</div>}
                    </td>
                    <td className="px-2 py-2">
                      <StatusBadge status={c.status} />
                    </td>
                    <td className="px-2 py-2 text-right font-mono">{formatNumber(c.n_documents)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatNumber(c.n_entities)}</td>
                    <td className="px-2 py-2 text-right font-mono">{formatNumber(c.n_edges)}</td>
                    <td className="px-2 py-2 font-mono text-[11px] text-muted">{formatDate(c.updated_at)}</td>
                    <td className="px-4 py-2">
                      <div className="flex justify-end gap-1">
                        <button type="button" className="btn btn-sm" disabled={busy || c.status === "processing" || c.status === "queued"} onClick={() => processCorpus.mutate(c.slug)} title="Run chunking, extraction and graph construction">
                          {c.status === "ready" ? "Reprocess" : "Process"}
                        </button>
                        <button type="button" className="btn btn-sm" disabled={busy} onClick={() => updateCorpus.mutate({ slug: c.slug, body: { visible: !c.visible } })}>
                          {c.visible ? "Hide" : "Show"}
                        </button>
                        <button
                          type="button"
                          className="btn btn-sm btn-danger"
                          disabled={busy}
                          onClick={() => {
                            if (window.confirm(`Delete “${c.title}” and all of its data?`)) deleteCorpus.mutate(c.slug);
                          }}
                        >
                          Delete
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          <div className="panel-head border-t border-line-soft">Processing jobs</div>
          <div className="px-4 py-2">
            {jobs.data && jobs.data.length === 0 && <div className="py-2 text-[13px] text-muted">No jobs yet.</div>}
            {jobs.data?.slice(0, 12).map((job) => (
              <JobProgress key={job.id} job={job} />
            ))}
          </div>
        </Panel>

        <Panel
          title="New corpus"
          actions={
            <div className="flex gap-1 normal-case tracking-normal">
              {(["paste", "upload"] as const).map((t) => (
                <button key={t} type="button" className={`rounded-sm px-2 py-0.5 ${tab === t ? "bg-pop-soft text-ink" : "hover:text-ink"}`} onClick={() => setTab(t)}>
                  {t === "paste" ? "Paste text" : "Upload files"}
                </button>
              ))}
            </div>
          }
        >
          <div className="p-4">
            {tab === "paste" ? (
              <PasteCorpusForm onCreated={(c) => setNotice(`Created “${c.title}” (${c.status}).`)} />
            ) : (
              <UploadCorpusForm onCreated={(c) => setNotice(`Uploaded “${c.title}” with ${c.n_documents} document(s).`)} />
            )}
          </div>
        </Panel>
      </div>
    </div>
  );
}
