import { useEffect } from "react";

export const SITE_TITLE = "ECCE · Entity-centric corpus exploration";

interface DocumentMeta {
  title: string;
  description?: string;
  /** Canonical path ("/", "/corpus/alice"); query strings such as ?page= are left out. */
  path?: string;
  noindex?: boolean;
}

function headElement<T extends HTMLElement>(selector: string, create: () => T): T {
  let element = document.head.querySelector<T>(selector);
  if (!element) {
    element = create();
    document.head.appendChild(element);
  }
  return element;
}

function setMeta(attribute: "name" | "property", key: string, content: string) {
  headElement(`meta[${attribute}="${key}"]`, () => {
    const meta = document.createElement("meta");
    meta.setAttribute(attribute, key);
    return meta;
  }).setAttribute("content", content);
}

/**
 * Keep the head in sync with the current page after client-side navigation. The server renders
 * the same tags into the first response (backend `services/seo.py`); this mirrors them so titles,
 * canonical links and robots hints stay right while the app routes without reloading.
 */
export function useDocumentMeta({ title, description, path, noindex = false }: DocumentMeta) {
  useEffect(() => {
    document.title = title;
    setMeta("property", "og:title", title);
    setMeta("name", "twitter:title", title);
    if (description) {
      setMeta("name", "description", description);
      setMeta("property", "og:description", description);
      setMeta("name", "twitter:description", description);
    }

    const robots = document.head.querySelector('meta[name="robots"]');
    const canonical = document.head.querySelector<HTMLLinkElement>('link[rel="canonical"]');
    if (noindex || path === undefined) {
      if (noindex) setMeta("name", "robots", "noindex");
      canonical?.remove();
      return;
    }
    robots?.remove();
    // keep the server's canonical origin (PUBLIC_URL) rather than whatever host served the page
    const origin = canonical ? new URL(canonical.href).origin : window.location.origin;
    const url = origin + path;
    headElement('link[rel="canonical"]', () => {
      const link = document.createElement("link");
      link.rel = "canonical";
      return link;
    }).href = url;
    setMeta("property", "og:url", url);
  }, [title, description, path, noindex]);
}

/** Collapse whitespace and cut at a word boundary (search snippets show ~160 characters). */
export function shorten(text: string, limit = 160): string {
  const clean = text.replace(/\s+/g, " ").trim();
  if (clean.length <= limit) return clean;
  return clean.slice(0, limit - 1).replace(/\s+\S*$/, "").replace(/[,;:·—-]+$/, "") + "…";
}
