/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // every colour is a CSS variable (RGB channels) so the dark theme can swap them, see index.css
        bg: { DEFAULT: "rgb(var(--c-bg) / <alpha-value>)", 2: "rgb(var(--c-bg-2) / <alpha-value>)" },
        surface: "rgb(var(--c-surface) / <alpha-value>)",
        sidebar: "rgb(var(--c-bg) / <alpha-value>)",
        ink: { DEFAULT: "rgb(var(--c-ink) / <alpha-value>)", 2: "rgb(var(--c-ink-2) / <alpha-value>)" },
        muted: { DEFAULT: "rgb(var(--c-muted) / <alpha-value>)", 2: "rgb(var(--c-muted-2) / <alpha-value>)" },
        line: { DEFAULT: "rgb(var(--c-line) / <alpha-value>)", soft: "rgb(var(--c-line-soft) / <alpha-value>)" },
        accent: { DEFAULT: "rgb(var(--c-accent) / <alpha-value>)", deep: "rgb(var(--c-accent-deep) / <alpha-value>)", soft: "rgb(var(--c-accent-soft) / <alpha-value>)" },
        select: "rgb(var(--c-select) / <alpha-value>)",
        pop: { DEFAULT: "rgb(var(--c-pop) / <alpha-value>)", soft: "rgb(var(--c-pop-soft) / <alpha-value>)" },
        warn: { DEFAULT: "rgb(var(--c-warn) / <alpha-value>)", soft: "rgb(var(--c-warn-soft) / <alpha-value>)" },
        danger: { DEFAULT: "rgb(var(--c-danger) / <alpha-value>)", soft: "rgb(var(--c-danger-soft) / <alpha-value>)" },
        violet: { DEFAULT: "rgb(var(--c-violet) / <alpha-value>)", soft: "rgb(var(--c-violet-soft) / <alpha-value>)" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        serif: ['"Source Serif 4 Variable"', '"Source Serif 4"', "Georgia", '"Iowan Old Style"', '"Palatino Linotype"', "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { sm: "0.25rem", md: "0.375rem", lg: "0.5rem" },
      maxWidth: { "4xl": "56rem" },
    },
  },
  plugins: [],
};
