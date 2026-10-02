import { useEffect, useRef } from "react";

export const LINKS = {
  paper: "https://doi.org/10.1145/3487553.3524237",
  code: "https://github.com/julianschelb/ecce",
  package: "https://pypi.org/project/implicit-word-network/",
  packageDocs: "https://julianschelb.github.io/implicit-word-network/",
  author: "https://julian-schelb.com",
  load: "https://doi.org/10.1145/2911451.2911529",
  thesis: "https://doi.org/10.11588/HEIDOK.00026328",
  gutenberg: "https://www.gutenberg.org/",
  perseus: "https://github.com/PerseusDL/canonical-latinLit",
  ccBySa: "https://creativecommons.org/licenses/by-sa/4.0/",
  notice: "https://github.com/julianschelb/ecce/blob/main/backend/data/seed/NOTICE.md",
  thirdParty: "https://github.com/julianschelb/ecce/blob/main/THIRD_PARTY_NOTICES.md",
};

function Ext({ href, children }: { href: string; children: React.ReactNode }) {
  return (
    <a className="text-accent-deep underline decoration-accent/40 underline-offset-2 hover:decoration-accent-deep" href={href} target="_blank" rel="noreferrer">
      {children}
    </a>
  );
}

/** Credits, references and licences, opened from the header (replaces the old page footer). */
export function AboutDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog ref={ref} className="about" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()} aria-labelledby="about-title">
      <div className="about__body">
        <div className="flex items-start justify-between gap-4">
          <h2 id="about-title" className="text-[22px] leading-tight">
            About ECCE
          </h2>
          <button type="button" className="btn btn-sm" onClick={onClose} aria-label="Close">
            Close
          </button>
        </div>
        <p className="mt-3 text-[14px] leading-relaxed text-ink-2">
          ECCE (entity-centric corpus exploration) turns a book into an <em>implicit entity network</em>: entities mentioned close to each other are linked, and the strength of a link decays with the distance between their mentions. The graph is a way to read: every link leads back to the pages it was built from.
        </p>
        <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-2.5 text-[13.5px]">
          <dt className="label mb-0 pt-0.5">Paper</dt>
          <dd>
            Julian Schelb, Maud Ehrmann, Matteo Romanello and Andreas Spitz (2022). <Ext href={LINKS.paper}>ECCE: Entity-centric Corpus Exploration Using Contextual Implicit Networks</Ext>. <em>WWW ’22 Companion</em>.
          </dd>
          <dt className="label mb-0 pt-0.5">Model</dt>
          <dd>
            Implicit entity networks after Andreas Spitz and Michael Gertz: <Ext href={LINKS.load}>Terms over LOAD</Ext> (SIGIR ’16) and Spitz’s thesis <Ext href={LINKS.thesis}>Implicit Entity Networks: A Versatile Document Model</Ext> (2019).
          </dd>
          <dt className="label mb-0 pt-0.5">Package</dt>
          <dd>
            <Ext href={LINKS.package}>implicit-word-network</Ext> on PyPI (<Ext href={LINKS.packageDocs}>documentation</Ext>), with spaCy and LatinCy for entity recognition.
          </dd>
          <dt className="label mb-0 pt-0.5">Code</dt>
          <dd>
            <Ext href={LINKS.code}>github.com/julianschelb/ecce</Ext>, MIT licence; <Ext href={LINKS.thirdParty}>third-party notices</Ext> and <Ext href="/licenses/third-party-npm.txt">bundled licences</Ext>.
          </dd>
          <dt className="label mb-0 pt-0.5">Texts</dt>
          <dd>
            English works are public-domain texts obtained from <Ext href={LINKS.gutenberg}>Project Gutenberg</Ext>: every author and translator died in 1955 or earlier and every work was first published before 1931. Project Gutenberg’s licence and the notes its volunteers added were removed.{" "}
            The Latin works (Vergil, Cicero, Horace, Ovid and others, each from a printed edition published before 1931) come from the <Ext href={LINKS.perseus}>Perseus Digital Library</Ext> (canonical-latinLit) under the <Ext href={LINKS.ccBySa}>CC BY-SA 4.0</Ext> licence; we split them into documents and passages and annotated their entities with LatinCy, and share these adapted corpora under the same licence. Each book names its source on the inside of its cover; see the <Ext href={LINKS.notice}>licence notice</Ext> for details.
          </dd>
          <dt className="label mb-0 pt-0.5">Author</dt>
          <dd>
            <Ext href={LINKS.author}>Julian Schelb</Ext>, University of Konstanz.
          </dd>
        </dl>
      </div>
    </dialog>
  );
}
