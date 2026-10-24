// Applies the remembered (or the system's) colour theme before the first paint, so the page never
// flashes light before turning dark. The key is shared with src/hooks/useTheme.ts.
(function () {
  try {
    var theme = localStorage.getItem("ecce-theme");
    if (theme !== "dark" && theme !== "light") {
      theme = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.dataset.theme = theme;
    var meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.setAttribute("content", theme === "dark" ? "#332f45" : "#f7f6f2");
  } catch (e) {
    /* storage unavailable: the stylesheet's light default applies */
  }
})();
