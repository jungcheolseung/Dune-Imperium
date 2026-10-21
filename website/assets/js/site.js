(() => {
  "use strict";

  const root = document.documentElement;
  const themeButton = document.querySelector(".theme-toggle");
  const systemTheme = matchMedia("(prefers-color-scheme: dark)");
  let themePreference = root.dataset.themePreference || "system";
  const applyTheme = () => {
    const dark = themePreference === "dark" || (themePreference === "system" && systemTheme.matches);
    root.dataset.theme = dark ? "dark" : "light";
    root.dataset.themePreference = themePreference;
    document.querySelector('meta[name="theme-color"]').content = dark ? "#111b1a" : "#f8f6ef";
    if (themeButton) {
      const label = dark ? themeButton.dataset.lightLabel : themeButton.dataset.darkLabel;
      themeButton.setAttribute("aria-label", label);
      themeButton.setAttribute("title", label);
      themeButton.setAttribute("aria-pressed", String(dark));
    }
  };
  if (themeButton) {
    themeButton.hidden = false;
    themeButton.addEventListener("click", () => {
      themePreference = root.dataset.theme === "dark" ? "light" : "dark";
      try { localStorage.setItem("dune-site-theme", themePreference); } catch { /* Optional persistence. */ }
      applyTheme();
    });
  }
  systemTheme.addEventListener("change", () => { if (themePreference === "system") applyTheme(); });
  addEventListener("storage", (event) => {
    if (event.key === "dune-site-theme" || event.key === null) {
      themePreference = event.newValue === "light" || event.newValue === "dark" ? event.newValue : "system";
      applyTheme();
    }
  });
  applyTheme();

  const menu = document.querySelector(".mobile-nav");
  if (menu) {
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && menu.open) {
        menu.open = false;
        menu.querySelector("summary").focus();
      }
    });
    document.addEventListener("click", (event) => {
      if (menu.open && !menu.contains(event.target)) menu.open = false;
    });
  }

  const form = document.querySelector("[data-search-index]");
  if (!form) return;
  document.querySelector("[data-search-fallback]").hidden = true;
  const input = form.querySelector("input");
  const status = document.getElementById("search-status");
  const results = document.getElementById("search-results");
  const message = (key, query = "", count = 0) => form.getAttribute(`data-${key}`)
    .replaceAll("{count}", String(count)).replaceAll("{query}", query);
  let indexPromise;
  let version = 0;
  let composing = false;
  let timer;
  const normalize = (value) => value.normalize("NFKC").toLocaleLowerCase(document.documentElement.lang);

  async function search() {
    const request = ++version;
    const query = input.value.trim();
    results.replaceChildren();
    const url = new URL(location.href);
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    history.replaceState(null, "", url);
    if (!query) {
      status.textContent = message("queryempty");
      return;
    }
    status.textContent = message("queryloading");
    try {
      if (!indexPromise) {
        indexPromise = fetch(form.dataset.searchIndex).then((response) => {
          if (!response.ok) throw new Error("search index unavailable");
          return response.json();
        }).catch((error) => { indexPromise = undefined; throw error; });
      }
      const index = await indexPromise;
      if (request !== version || composing) return;
      const terms = normalize(query).split(/\s+/u);
      const matches = index.map((page) => {
        const title = normalize(page.title);
        const description = normalize(page.description);
        const text = `${title} ${description} ${normalize(page.text)}`;
        return { page, found: terms.every((term) => text.includes(term)), score: terms.reduce((score, term) => score + (title.includes(term) ? 5 : 0) + (description.includes(term) ? 2 : 0), 0) };
      }).filter((item) => item.found).sort((a, b) => b.score - a.score);
      status.textContent = message(matches.length ? "queryresults" : "querynone", query, matches.length);
      for (const { page } of matches) {
        const item = document.createElement("li");
        const title = document.createElement("h2");
        const link = document.createElement("a");
        const target = new URL(page.url, location.origin);
        if (target.origin !== location.origin) continue;
        link.href = target.href;
        link.textContent = page.title;
        title.append(link);
        const description = document.createElement("p");
        description.textContent = page.description;
        item.append(title, description);
        results.append(item);
      }
    } catch {
      if (request === version) status.textContent = message("queryerror");
    }
  }

  input.addEventListener("compositionstart", () => { composing = true; version++; clearTimeout(timer); });
  input.addEventListener("compositionend", () => { composing = false; clearTimeout(timer); timer = setTimeout(search, 120); });
  input.addEventListener("input", () => { clearTimeout(timer); if (!composing) timer = setTimeout(search, 120); });
  form.addEventListener("submit", (event) => { event.preventDefault(); clearTimeout(timer); if (!composing) search(); });
  document.addEventListener("keydown", (event) => {
    if (event.key === "/" && !event.isComposing && !/^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName)) {
      event.preventDefault(); input.focus();
    }
  });
  input.value = new URLSearchParams(location.search).get("q")?.slice(0, 160) || "";
  if (input.value) search();
})();
