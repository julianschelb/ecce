import { useMemo, useSyncExternalStore } from "react";

export type Theme = "light" | "dark";

const KEY = "ecce-theme"; // also read by public/theme-init.js before the first paint
const THEME_COLOR: Record<Theme, string> = { light: "#f7f6f2", dark: "#16181c" };

function systemTheme(): Theme {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function storedTheme(): Theme | null {
  try {
    const value = localStorage.getItem(KEY);
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null;
  }
}

function apply(theme: Theme) {
  document.documentElement.dataset.theme = theme;
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
}

let current: Theme = storedTheme() ?? systemTheme();
apply(current);
const listeners = new Set<() => void>();

function set(theme: Theme) {
  current = theme;
  apply(theme);
  listeners.forEach((listener) => listener());
}

// without an explicit choice the site follows the system setting, live
if (typeof matchMedia === "function") {
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
    if (!storedTheme()) set(systemTheme());
  });
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** The current colour theme and a way to switch it; the choice is remembered in this browser. */
export function useTheme() {
  const theme = useSyncExternalStore(subscribe, () => current, () => "light" as Theme);
  const setTheme = (next: Theme) => {
    try {
      localStorage.setItem(KEY, next);
    } catch {
      /* private mode: the choice lasts for this page view */
    }
    set(next);
  };
  return { theme, setTheme, toggle: () => setTheme(theme === "dark" ? "light" : "dark") };
}

function channelsToHex(channels: string, fallback: string): string {
  const parts = channels.trim().split(/\s+/).map(Number);
  if (parts.length !== 3 || parts.some(Number.isNaN)) return fallback;
  return "#" + parts.map((n) => n.toString(16).padStart(2, "0")).join("");
}

/** Theme colours as hex strings for canvas and SVG drawing, which cannot use CSS variables. */
export function useThemeColors() {
  const { theme } = useTheme();
  return useMemo(() => {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string, fallback: string) => channelsToHex(style.getPropertyValue(name), fallback);
    return {
      ink: read("--c-ink", "#1f2328"),
      surface: read("--c-bg", "#f7f6f2"),
      accentDeep: read("--c-accent-deep", "#33618f"),
    };
  }, [theme]);
}
