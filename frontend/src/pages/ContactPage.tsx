import { useState, type FormEvent } from "react";
import { ErrorNote } from "@/components/ui";
import { useSendMessage } from "@/hooks/useApi";
import { useDocumentMeta } from "@/hooks/useDocumentMeta";

/** Contact form: the second contact channel of the legal notice (§ 5 DDG). */
export function ContactPage() {
  useDocumentMeta({ title: "Contact · ECCE", description: "Send a message to the operator of this site.", path: "/contact" });
  const send = useSendMessage();
  const [form, setForm] = useState({ name: "", email: "", message: "", website: "" });
  const set = (key: keyof typeof form, value: string) => setForm((f) => ({ ...f, [key]: value }));

  function submit(event: FormEvent) {
    event.preventDefault();
    send.mutate(form, { onSuccess: () => setForm({ name: "", email: "", message: "", website: "" }) });
  }

  return (
    <div className="mx-auto max-w-[640px] px-6 py-10">
      <h1 className="text-[30px]">Contact</h1>
      <p className="mt-2 text-[15px] leading-[1.6] text-ink-2">
        Questions, corrections or requests about this site? Write to the operator named in the <a className="text-accent-deep underline" href="/legal">legal notice</a>.
      </p>
      {send.isSuccess ? (
        <div className="mt-6 rounded-md border border-accent/40 bg-accent-soft px-4 py-3 text-[14px] text-accent-deep">
          Thank you, your message has been received. You will get an answer at the e-mail address you entered.
        </div>
      ) : (
        <form onSubmit={submit} className="mt-6 space-y-4">
          <div>
            <label className="label" htmlFor="contact-name">
              Name (optional)
            </label>
            <input id="contact-name" className="input" value={form.name} onChange={(e) => set("name", e.target.value)} maxLength={120} autoComplete="name" />
          </div>
          <div>
            <label className="label" htmlFor="contact-email">
              E-mail (for the answer)
            </label>
            <input id="contact-email" className="input" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} required maxLength={254} autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="contact-message">
              Message
            </label>
            <textarea id="contact-message" className="input min-h-[180px]" value={form.message} onChange={(e) => set("message", e.target.value)} required minLength={10} maxLength={5000} />
          </div>
          {/* honeypot for spam bots: hidden from people and assistive technology */}
          <div className="hidden" aria-hidden>
            <label htmlFor="contact-website">Website</label>
            <input id="contact-website" tabIndex={-1} autoComplete="off" value={form.website} onChange={(e) => set("website", e.target.value)} />
          </div>
          <p className="text-[12.5px] leading-[1.5] text-muted">
            Your message is stored on this site’s server only to answer you and is deleted after it has been dealt with. See the <a className="underline" href="/privacy">privacy policy</a>.
          </p>
          {send.error && <ErrorNote error={send.error} />}
          <button type="submit" className="btn btn-primary" disabled={send.isPending}>
            {send.isPending ? "Sending…" : "Send message"}
          </button>
        </form>
      )}
    </div>
  );
}
