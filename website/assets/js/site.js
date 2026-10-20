(() => {
  "use strict";

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
  let indexPromise;
  let version = 0;
  let composing = false;
  let timer;
  const normalize = (value) => value.normalize("NFKC").toLocaleLowerCase("ko");

  async function search() {
    const request = ++version;
    const query = input.value.trim();
    results.replaceChildren();
    const url = new URL(location.href);
    if (query) url.searchParams.set("q", query);
    else url.searchParams.delete("q");
    history.replaceState(null, "", url);
    if (!query) {
      status.textContent = "검색어를 입력해 주세요.";
      return;
    }
    status.textContent = "찾고 있습니다…";
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
      status.textContent = matches.length ? `“${query}” 검색 결과 ${matches.length}개` : `“${query}” 검색 결과가 없습니다. 다른 단어로 찾아보세요.`;
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
      if (request === version) status.textContent = "검색 자료를 불러오지 못했습니다. 다시 검색하거나 아래 안내를 이용해 주세요.";
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
