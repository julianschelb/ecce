import { useState, type FormEvent } from "react";
import { useAdminMutations, useJob } from "@/hooks/useApi";
import { ApiError, type CorpusSummary, type JobOut } from "@/lib/api";
import { StatusBadge } from "@/components/ui";

function errorText(error: unknown): string {
  return error instanceof ApiError ? error.message : error instanceof Error ? error.message : "Request failed";
}

const META_FIELDS = [
  ["genre", "Genre", "Fiction, News, Letters…"],
  ["source", "Source", "Project Gutenberg #11"],
] as const;

export function PasteCorpusForm({ onCreated }: { onCreated: (corpus: CorpusSummary) => void }) {
  const { createCorpus } = useAdminMutations();
  const [form, setForm] = useState({ title: "", text: "", description: "", genre: "", source: "", split: "auto", visible: true, process: true });
  const set = (key: keyof typeof form, value: string | boolean) => setForm((f) => ({ ...f, [key]: value }));

  async function submit(event: FormEvent) {
    event.preventDefault();
    const corpus = await createCorpus.mutateAsync(form);
    setForm((f) => ({ ...f, title: "", text: "", description: "" }));
    onCreated(corpus);
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="label">Title</label>
        <input className="input" value={form.title} onChange={(e) => set("title", e.target.value)} required maxLength={200} />
      </div>
      <div>
        <label className="label">Text</label>
        <textarea className="input min-h-[180px] font-serif" value={form.text} onChange={(e) => set("text", e.target.value)} placeholder="Paste the raw text. Chapters or Markdown headings become separate documents." required />
      </div>
      <div className="grid grid-cols-2 gap-3">
        {META_FIELDS.map(([key, label, placeholder]) => (
          <div key={key}>
            <label className="label">{label}</label>
            <input className="input" value={form[key]} onChange={(e) => set(key, e.target.value)} placeholder={placeholder} />
          </div>
        ))}
      </div>
      <div>
        <label className="label">Description</label>
        <input className="input" value={form.description} onChange={(e) => set("description", e.target.value)} />
      </div>
      <div className="flex flex-wrap items-center gap-4 text-[13px]">
        <label className="flex items-center gap-2">
          <span className="text-muted">Split</span>
          <select className="input w-auto" value={form.split} onChange={(e) => set("split", e.target.value)}>
            <option value="auto">auto (headings if present)</option>
            <option value="headings">at headings</option>
            <option value="none">single document</option>
          </select>
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={form.visible} onChange={(e) => set("visible", e.target.checked)} /> visible in gallery
        </label>
        <label className="flex items-center gap-1.5">
          <input type="checkbox" checked={form.process} onChange={(e) => set("process", e.target.checked)} /> process now
        </label>
      </div>
      {createCorpus.error && <div className="text-[13px] text-danger">{errorText(createCorpus.error)}</div>}
      <button type="submit" className="btn btn-primary" disabled={createCorpus.isPending}>
        {createCorpus.isPending ? "Creating…" : "Create corpus"}
      </button>
    </form>
  );
}

export function UploadCorpusForm({ onCreated }: { onCreated: (corpus: CorpusSummary) => void }) {
  const { uploadCorpus } = useAdminMutations();
  const [title, setTitle] = useState("");
  const [genre, setGenre] = useState("");
  const [source, setSource] = useState("");
  const [files, setFiles] = useState<FileList | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!files || files.length === 0) return;
    const form = new FormData();
    form.set("title", title);
    form.set("genre", genre);
    form.set("source", source);
    Array.from(files).forEach((file) => form.append("files", file));
    const corpus = await uploadCorpus.mutateAsync(form);
    setTitle("");
    setFiles(null);
    onCreated(corpus);
  }

  return (
    <form onSubmit={submit} className="space-y-3">
      <div>
        <label className="label">Title</label>
        <input className="input" value={title} onChange={(e) => setTitle(e.target.value)} required maxLength={200} />
      </div>
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="label">Genre</label>
          <input className="input" value={genre} onChange={(e) => setGenre(e.target.value)} />
        </div>
        <div>
          <label className="label">Source</label>
          <input className="input" value={source} onChange={(e) => setSource(e.target.value)} />
        </div>
      </div>
      <div>
        <label className="label">Files (.txt, .md — one document each)</label>
        <input className="input" type="file" multiple accept=".txt,.md,.markdown,text/plain,text/markdown" onChange={(e) => setFiles(e.target.files)} required />
        {files && <div className="mt-1 font-mono text-[11px] text-muted">{files.length} file(s) selected</div>}
      </div>
      {uploadCorpus.error && <div className="text-[13px] text-danger">{errorText(uploadCorpus.error)}</div>}
      <button type="submit" className="btn btn-primary" disabled={uploadCorpus.isPending || !files}>
        {uploadCorpus.isPending ? "Uploading…" : "Upload and process"}
      </button>
    </form>
  );
}

export function JobProgress({ job }: { job: JobOut }) {
  const live = useJob(job.status === "queued" || job.status === "running" ? job.id : null);
  const current = live.data ?? job;
  return (
    <div className="flex items-center gap-3 py-1.5 text-[13px]">
      <StatusBadge status={current.status} />
      <span className="w-40 truncate font-medium">{current.corpus_slug}</span>
      <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-line-soft">
        <div className={`h-full transition-all ${current.status === "failed" ? "bg-danger" : "bg-accent-deep"}`} style={{ width: `${Math.round(current.progress * 100)}%` }} />
      </div>
      <span className="w-48 truncate font-mono text-[11px] text-muted" title={current.error ?? current.message}>
        {current.error ?? current.message}
      </span>
    </div>
  );
}
