import { Link } from "react-router-dom";

/** Legal notice (§ 5 DDG), privacy policy (Art. 13 GDPR) and contact form: in the gallery's footer
 * and at the bottom of the About dialog, which every page reaches from the header. */
export function LegalLinks({ onNavigate, className = "" }: { onNavigate?: () => void; className?: string }) {
  const link = "text-muted underline-offset-2 hover:text-ink hover:underline";
  return (
    <nav aria-label="Legal" className={`flex flex-wrap items-center gap-x-4 gap-y-1 text-[12.5px] ${className}`}>
      <a href="/legal" className={link}>
        Legal notice
      </a>
      <a href="/privacy" className={link}>
        Privacy
      </a>
      <Link to="/contact" className={link} onClick={onNavigate}>
        Contact
      </Link>
    </nav>
  );
}

/** A link that opens in a new tab, marked with an external-link icon. */
export function ExternalIcon() {
  return (
    <svg viewBox="0 0 12 12" width="10" height="10" aria-hidden className="ml-0.5 inline-block align-[-0.05em]">
      <path d="M4.5 2.5H2.5v7h7v-2M7 2.5h2.5V5M9.5 2.5 5.5 6.5" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
