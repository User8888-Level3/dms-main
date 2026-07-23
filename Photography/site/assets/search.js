// THE ARCHIVE — client-side search + lightbox
//
// Search query syntax:
//   plain text          → substring match on filename + event + camera + date
//   year:YYYY           → restrict to year
//   kind:image|raw|video
//   has:gps             → only rows with GPS
//   sha1:<hex-prefix>   → match SHA-1 prefix
//   camera:<substr>     → substring match on camera name

(() => {
  // ───── DOM ─────
  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  const searchEl    = $("#search");
  const statusEl    = $("#search-status");
  const browseEl    = $("#browse");
  const resultsEl   = $("#results");
  const resultsHdr  = $("#results-header");
  const resultsGrid = $("#results-grid");
  const resultsClear = $("#results-clear");
  const lightbox    = $("#lightbox");

  // Page context: home OR year (for relative path to assets/)
  const pageKind   = document.body.dataset.page || "home";
  const inYearPage = pageKind === "year";
  const assetsBase = inYearPage ? "../assets" : "assets";
  const thumbBase  = inYearPage ? "../thumbs" : "thumbs";

  let manifest = null;            // { thumb_root, years: [...] }
  const yearCache = new Map();    // year → array of rows
  let activeRequest = 0;
  let currentList = [];           // rows currently displayed (year page or search)
  let currentIndex = -1;          // index into currentList for lightbox
  let preloadedYears = new Set();

  // ────────── INIT ──────────
  init().catch(err => {
    console.error("search init failed", err);
    if (statusEl) statusEl.textContent = "search unavailable";
  });

  async function init() {
    const r = await fetch(`${assetsBase}/search-manifest.json`);
    manifest = await r.json();

    if (searchEl) searchEl.addEventListener("input", debounce(runSearch, 120));
    if (resultsClear) resultsClear.addEventListener("click", clearSearch);

    // Year page: populate currentList from this year's data so lightbox works
    if (inYearPage) {
      const year = Number(document.body.dataset.year);
      try {
        const yearMeta = manifest.years.find(y => y.year === year);
        if (yearMeta) {
          currentList = await loadYear(yearMeta);
          // Bind click handlers to the rendered photo tiles for this year
          bindPhotoTiles();
          setupEventNavObserver();
        }
      } catch (e) {
        console.warn("could not load year data for lightbox", e);
      }
    }

    // Lightbox handlers
    setupLightbox();

    // Keyboard shortcuts
    document.addEventListener("keydown", onGlobalKey);

    // Hash deep-link to a photo
    if (location.hash.startsWith("#photo-")) {
      const id = Number(location.hash.slice(7));
      openLightboxById(id);
    }

    // ?q= deep link for search
    const q = new URL(location.href).searchParams.get("q");
    if (q && searchEl) { searchEl.value = q; runSearch(); }
  }

  // ────────── SEARCH ──────────

  function debounce(fn, ms) {
    let t = null;
    return (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  }

  async function runSearch() {
    const raw = (searchEl?.value || "").trim();
    if (!raw) { clearSearch(); return; }

    if (browseEl) browseEl.hidden = true;
    resultsEl.hidden = false;

    const filters = parseQuery(raw);
    const req = ++activeRequest;
    if (statusEl) statusEl.textContent = "searching…";

    const yearsToLoad = filters.year
      ? manifest.years.filter(y => y.year === filters.year)
      : manifest.years;

    const allRows = [];
    for (const y of yearsToLoad) {
      const rows = await loadYear(y);
      if (req !== activeRequest) return;
      allRows.push(...rows);
    }
    const matches = allRows.filter(r => matchRow(r, filters));
    render(matches, raw);
  }

  function clearSearch() {
    if (searchEl) searchEl.value = "";
    resultsEl.hidden = true;
    if (browseEl) browseEl.hidden = false;
    if (statusEl) statusEl.textContent = "";

    // Restore year-page lightbox list
    if (inYearPage) {
      const year = Number(document.body.dataset.year);
      const cached = yearCache.get(year);
      if (cached) currentList = cached;
    }
  }

  function parseQuery(raw) {
    const f = { year: null, kind: null, hasGps: false, sha1: null, camera: null, terms: [] };
    for (const tok of raw.split(/\s+/).filter(Boolean)) {
      const m = tok.match(/^([a-zA-Z]+):(.*)$/);
      if (m) {
        const key = m[1].toLowerCase();
        const val = m[2];
        if (key === "year" && /^\d{4}$/.test(val)) f.year = Number(val);
        else if (key === "kind") f.kind = val.toLowerCase();
        else if (key === "has" && val.toLowerCase() === "gps") f.hasGps = true;
        else if (key === "sha1") f.sha1 = val.toLowerCase();
        else if (key === "camera") f.camera = val.toLowerCase();
        else f.terms.push(tok.toLowerCase());
      } else {
        f.terms.push(tok.toLowerCase());
      }
    }
    return f;
  }

  function matchRow(r, f) {
    if (f.kind && r.k !== f.kind) return false;
    if (f.hasGps && !r.g) return false;
    if (f.sha1 && !(r.sha1 || "").startsWith(f.sha1)) return false;
    if (f.camera && !(r.c || "").toLowerCase().includes(f.camera)) return false;
    for (const t of f.terms) {
      const haystack = [r.f, r.e, r.d || "", r.c || "", String(r.y || "")].join(" ").toLowerCase();
      if (!haystack.includes(t)) return false;
    }
    return true;
  }

  async function loadYear(y) {
    if (yearCache.has(y.year)) return yearCache.get(y.year);
    const r = await fetch(inYearPage ? `../${y.file}` : y.file);
    const data = await r.json();
    for (const row of data) row.y = y.year;
    yearCache.set(y.year, data);
    preloadedYears.add(y.year);
    return data;
  }

  function render(matches, rawQuery) {
    resultsHdr.textContent =
      matches.length === 0
        ? `Nothing matched "${rawQuery}"`
        : `${matches.length.toLocaleString()} ${matches.length === 1 ? "result" : "results"} for "${rawQuery}"`;
    resultsGrid.replaceChildren();
    if (statusEl) statusEl.textContent = `${matches.length.toLocaleString()} matches`;

    const LIMIT = 2000;
    const rows = matches.slice(0, LIMIT);
    currentList = rows;

    const frag = document.createDocumentFragment();
    rows.forEach((r, i) => {
      const a = document.createElement("a");
      a.className = "result-tile";
      a.href = `#photo-${r.id}`;
      a.dataset.photoId = r.id;
      a.dataset.year = r.y;
      a.dataset.idx = i;
      a.title = `${r.f} · ${r.e} · ${r.y}${r.d ? " · " + r.d : ""}`;
      const img = document.createElement("img");
      img.loading = "lazy";
      img.src = `${thumbBase}/${r.t}`;
      img.alt = "";
      a.appendChild(img);
      if (r.k === "video") {
        const b = document.createElement("span");
        b.className = "badge badge--video";
        b.textContent = "▶ VIDEO";
        a.appendChild(b);
      } else if (r.k === "raw") {
        const b = document.createElement("span");
        b.className = "badge badge--raw";
        b.textContent = "RAW";
        a.appendChild(b);
      }
      a.addEventListener("click", (ev) => {
        ev.preventDefault();
        openLightboxAt(i);
      });
      frag.appendChild(a);
    });
    if (matches.length > LIMIT) {
      const note = document.createElement("div");
      note.style.cssText = "padding: 16px 0; color: var(--ink-muted); font-size: 12px; font-family: var(--font-mono);";
      note.textContent = `Showing first ${LIMIT.toLocaleString()} of ${matches.length.toLocaleString()} — refine your search.`;
      resultsGrid.appendChild(note);
    }
    resultsGrid.appendChild(frag);
  }

  // ────────── PHOTO TILES (year page) ──────────

  function bindPhotoTiles() {
    const tiles = $$(".photo-tile[data-photo-id]");
    tiles.forEach((tile, idx) => {
      const id = Number(tile.dataset.photoId);
      const i = currentList.findIndex(r => r.id === id);
      if (i >= 0) tile.dataset.idx = i;
      tile.addEventListener("click", (ev) => {
        ev.preventDefault();
        if (i >= 0) openLightboxAt(i);
      });
    });
  }

  // Highlight the current event in the sidebar nav
  function setupEventNavObserver() {
    const links = $$(".event-nav__list a[data-event-link]");
    if (!links.length) return;
    const linkBySlug = new Map(links.map(a => [a.dataset.eventLink, a]));

    const obs = new IntersectionObserver((entries) => {
      // Find the topmost intersecting event
      const visible = entries
        .filter(e => e.isIntersecting)
        .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0];
      if (!visible) return;
      const slug = visible.target.id.replace(/^evt-/, "");
      links.forEach(a => a.classList.remove("is-active"));
      const a = linkBySlug.get(slug);
      if (a) a.classList.add("is-active");
    }, { rootMargin: "-90px 0px -60% 0px", threshold: 0 });

    $$(".event[id^='evt-']").forEach(el => obs.observe(el));

    // Smooth scroll on click
    links.forEach(a => {
      a.addEventListener("click", (ev) => {
        const href = a.getAttribute("href");
        if (!href || !href.startsWith("#")) return;
        const target = document.getElementById(href.slice(1));
        if (target) {
          ev.preventDefault();
          target.scrollIntoView({ behavior: "smooth", block: "start" });
          history.replaceState(null, "", href);
        }
      });
    });
  }

  // ────────── LIGHTBOX ──────────

  function setupLightbox() {
    if (!lightbox) return;
    lightbox.querySelectorAll("[data-close]").forEach(el => el.addEventListener("click", closeLightbox));
    lightbox.querySelector("[data-prev]")?.addEventListener("click", () => navLightbox(-1));
    lightbox.querySelector("[data-next]")?.addEventListener("click", () => navLightbox(+1));
    lightbox.querySelectorAll(".copy-btn").forEach(btn => {
      btn.addEventListener("click", () => copyField(btn));
    });
    lightbox.querySelectorAll(".action-btn[data-action]").forEach(btn => {
      btn.addEventListener("click", () => triggerAction(btn));
    });
  }

  async function triggerAction(btn) {
    if (btn.classList.contains("is-busy")) return;
    const action = btn.dataset.action;                 // "open" | "reveal"
    const pathEl = lightbox.querySelector('[data-field="path"]');
    const path = pathEl?.textContent?.trim();
    if (!path || path === "—") { flashState(btn, "is-err", "no path"); return; }

    const origLabel = btn.querySelector(".action-btn__label")?.textContent;
    btn.classList.add("is-busy");
    try {
      const r = await fetch(`/api/${action}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path }),
      });
      btn.classList.remove("is-busy");
      if (r.ok) {
        flashState(btn, "is-ok", action === "reveal" ? "revealed" : "opened");
      } else {
        let msg = "failed";
        try { const j = await r.json(); if (j.error) msg = j.error; } catch (_) {}
        flashState(btn, "is-err", msg);
      }
    } catch (e) {
      btn.classList.remove("is-busy");
      flashState(btn, "is-err", "server offline");
    }
    // Restore original label after the flash window
    setTimeout(() => {
      const lbl = btn.querySelector(".action-btn__label");
      if (lbl && origLabel) lbl.textContent = origLabel;
    }, 1600);
  }

  function flashState(btn, cls, text) {
    const lbl = btn.querySelector(".action-btn__label");
    if (lbl && text) lbl.textContent = text;
    btn.classList.add(cls);
    setTimeout(() => btn.classList.remove(cls), 1500);
  }

  function openLightboxAt(idx) {
    if (idx < 0 || idx >= currentList.length) return;
    currentIndex = idx;
    paintLightbox(currentList[idx]);
    lightbox.hidden = false;
    lightbox.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    history.replaceState(null, "", `#photo-${currentList[idx].id}`);
  }

  async function openLightboxById(id) {
    // Find in currentList first
    let idx = currentList.findIndex(r => r.id === id);
    if (idx >= 0) { openLightboxAt(idx); return; }

    // Otherwise scan loaded years; if still nothing, nothing to do (deep-link
    // came from a different page or the file has been removed).
    for (const rows of yearCache.values()) {
      idx = rows.findIndex(r => r.id === id);
      if (idx >= 0) { currentList = rows; openLightboxAt(idx); return; }
    }
  }

  function navLightbox(delta) {
    if (!currentList.length) return;
    currentIndex = (currentIndex + delta + currentList.length) % currentList.length;
    paintLightbox(currentList[currentIndex]);
    history.replaceState(null, "", `#photo-${currentList[currentIndex].id}`);
  }

  function closeLightbox() {
    lightbox.hidden = true;
    lightbox.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
    if (location.hash.startsWith("#photo-")) {
      history.replaceState(null, "", location.pathname + location.search);
    }
  }

  function paintLightbox(row) {
    const img = lightbox.querySelector(".lightbox__image");
    img.src = `${thumbBase}/${row.t}`;
    img.alt = row.f || "";

    const cap = lightbox.querySelector(".lightbox__caption");
    cap.textContent = `${currentIndex + 1} of ${currentList.length}`;

    setField("filename", row.f || "—");
    setField("event", row.e ? `${row.e} · ${row.y}` : String(row.y || ""));
    setField("date", formatDate(row.d));
    setField("camera", row.c || "Unknown");
    setField("size", formatBytes(row.b));
    setField("dims", row.w && row.h ? `${row.w.toLocaleString()} × ${row.h.toLocaleString()} px` : "—");
    setField("ext", `${(row.k || "image").toUpperCase()} · ${ext(row.f)}`);
    setField("gps", row.g ? "Geotagged" : "Not present");
    setField("path", row.p || "—");
    setField("sha1", row.sha1 || "—");

    const kindEl = lightbox.querySelector("[data-kind]");
    if (kindEl) kindEl.textContent = (row.k || "image").toUpperCase();
  }

  function setField(name, value) {
    const el = lightbox.querySelector(`[data-field="${name}"]`);
    if (el) el.textContent = value;
  }

  function copyField(btn) {
    const which = btn.dataset.copy;
    const target = lightbox.querySelector(`[data-field="${which}"]`);
    if (!target) return;
    const text = target.textContent;
    navigator.clipboard.writeText(text).then(() => {
      const orig = btn.textContent;
      btn.textContent = "copied";
      btn.classList.add("is-copied");
      setTimeout(() => {
        btn.textContent = orig;
        btn.classList.remove("is-copied");
      }, 1300);
    }).catch(() => {
      btn.textContent = "copy failed";
      setTimeout(() => { btn.textContent = "copy"; }, 1300);
    });
  }

  function onGlobalKey(ev) {
    // Slash to focus search (when not in input)
    if (ev.key === "/" && document.activeElement?.tagName !== "INPUT") {
      if (searchEl) { ev.preventDefault(); searchEl.focus(); searchEl.select(); }
      return;
    }
    // Lightbox shortcuts
    if (lightbox && !lightbox.hidden) {
      if (ev.key === "Escape") { closeLightbox(); }
      else if (ev.key === "ArrowLeft") { navLightbox(-1); }
      else if (ev.key === "ArrowRight") { navLightbox(+1); }
      else if (ev.key === "c" || ev.key === "C") {
        const btn = lightbox.querySelector('.copy-btn[data-copy="path"]');
        if (btn) copyField(btn);
      }
      else if (ev.key === "f" || ev.key === "F") {
        const btn = lightbox.querySelector('.action-btn[data-action="reveal"]');
        if (btn) { ev.preventDefault(); triggerAction(btn); }
      }
      else if (ev.key === "o" || ev.key === "O") {
        const btn = lightbox.querySelector('.action-btn[data-action="open"]');
        if (btn) { ev.preventDefault(); triggerAction(btn); }
      }
    }
    // Esc to clear search
    else if (ev.key === "Escape" && document.activeElement === searchEl) {
      searchEl.value = "";
      clearSearch();
    }
  }

  // ────────── HELPERS ──────────

  function formatDate(iso) {
    if (!iso) return "Unknown";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      year: "numeric", month: "short", day: "numeric",
      hour: "numeric", minute: "2-digit",
    });
  }

  function formatBytes(n) {
    if (n == null) return "—";
    let x = Number(n);
    if (!isFinite(x)) return "—";
    const units = ["B", "KB", "MB", "GB", "TB"];
    let u = 0;
    while (x >= 1024 && u < units.length - 1) { x /= 1024; u++; }
    return `${x.toFixed(u === 0 ? 0 : 1)} ${units[u]}`;
  }

  function ext(filename) {
    if (!filename) return "—";
    const i = filename.lastIndexOf(".");
    return i >= 0 ? filename.slice(i + 1).toUpperCase() : "—";
  }
})();
