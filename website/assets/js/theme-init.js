(() => {
  let preference = "system";
  try {
    const saved = localStorage.getItem("dune-site-theme");
    if (saved === "light" || saved === "dark") preference = saved;
  } catch { /* Storage may be unavailable; the toggle still works. */ }
  const dark = preference === "dark" || (preference === "system" && matchMedia("(prefers-color-scheme: dark)").matches);
  document.documentElement.dataset.themePreference = preference;
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  document.querySelector('meta[name="theme-color"]').content = dark ? "#111b1a" : "#f8f6ef";
})();
