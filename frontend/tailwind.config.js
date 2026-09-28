/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#f7f6f2",
        surface: "#ffffff",
        sidebar: "#f7f6f2",
        ink: { DEFAULT: "#1f2328", 2: "#3d434b" },
        muted: "#6a707a",
        line: { DEFAULT: "#dcd9d0", soft: "#ecebe5" },
        accent: { DEFAULT: "#4f80b8", deep: "#33618f", soft: "#e3f2fd" },
        select: "#dfe7f1",
        pop: { DEFAULT: "#4a5a6e", soft: "#e8ecf1" },
        warn: { DEFAULT: "#8a6414", soft: "#f6efdd" },
        danger: { DEFAULT: "#9b3340", soft: "#f5e4e6" },
        violet: { DEFAULT: "#5e4a93", soft: "#ebe7f3" },
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "-apple-system", '"Segoe UI"', "sans-serif"],
        serif: ['"Source Serif 4"', "Georgia", '"Iowan Old Style"', '"Palatino Linotype"', "serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      borderRadius: { sm: "0.25rem", md: "0.375rem", lg: "0.5rem" },
      maxWidth: { "4xl": "56rem" },
    },
  },
  plugins: [],
};
