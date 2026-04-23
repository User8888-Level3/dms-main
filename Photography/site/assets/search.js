// Client-side search over per-year JSON exports.
//
// Query syntax:
//   plain text          → substring match on filename + event
//   year:YYYY           → restrict to year
//   kind:image|raw|video
//   has:gps             → only rows with GPS
//   sha1:<hex-prefix>   → match SHA-1 prefix
//   camera:<substr>     → substring match on camera name
// Free terms stack (AND). A plain date like "2024-05" also matches the date field.

const searchEl    = document.getElementById("search");
const statusEl    = document.getElementById("search-status");
const browseEl    = document.getElementById("browse");
const resultsEl   = document.getElementById("results");
const resultsHdr  = document.getElementById("results-header");
const resultsGrid = document.getElementById("results-grid");

let manifest = null;           // { thumb_root, years: [{year, count, file}] }
const yearCache = new Map();   // year → [rows]
let activeRequest = 0;

init();

async function init() {
  try {
    const r = await fetch("assets/search-manifest.json");
    manifest = await r.json();
  } catch (e) {
    statusEl.textContent = "search index unavailable";
    return;
  }
  searchEl.addEventListener("input", onInput);
  // Allow ?q= deep-linking
  const q = new URL(location.href).searchParams.get("q");
  if (q) { searchEl.value = q; onInput(); }
}

let debounceTimer = null;
function onInput() {
  clearTimeout(debounceTimer);
  debounceTimer = setTimeout(runSearch, 120);
}

async function runSearch() {
  const raw = searchEl.value.trim();
  if (!raw) {
    resultsEl.hidden = true;
    browseEl.hidden = false;
    statusEl.textContent = "";
    return;
  }
  browseEl.hidden = true;
  resultsEl.hidden = false;

  const filters = parseQuery(raw);
  const req = ++activeRequest;
  statusEl.textContent = "searching…";

  const yearsToLoad = filters.year
    ? manifest.years.filter(y => y.year === filters.year)
    : manifest.years;

  const allRows = [];
  for (const y of yearsToLoad) {
    const rows = await loadYear(y);
    if (req !== activeRequest) return;  // superseded
    allRows.push(...rows);
  }

  const matches = allRows.filter(r => matchRow(r, filters));
  render(matches, raw);
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
    const haystack = [r.f, r.e, r.d || "", r.c || ""].join(" ").toLowerCase();
    if (!haystack.includes(t)) return false;
  }
  return true;
}

async function loadYear(y) {
  if (yearCache.has(y.year)) return yearCache.get(y.year);
  const r = await fetch(y.file);
  const data = await r.json();
  for (const row of data) row.y = y.year;
  yearCache.set(y.year, data);
  return data;
}

function render(matches, rawQuery) {
  resultsHdr.textContent = `${matches.length} result${matches.length === 1 ? "" : "s"} for "${rawQuery}"`;
  resultsGrid.replaceChildren();
  statusEl.textContent = `${matches.length} / ${totalLoaded()} loaded`;

  const LIMIT = 2000;
  const rows = matches.slice(0, LIMIT);
  const frag = document.createDocumentFragment();
  for (const r of rows) {
    const a = document.createElement("a");
    a.className = "result-tile";
    a.href = `${manifest.thumb_root}/${r.t}`;
    a.target = "_blank";
    a.title = `${r.f}  ·  ${r.e}  ·  ${r.y}${r.d ? "  ·  " + r.d : ""}${r.c ? "  ·  " + r.c : ""}`;
    const img = document.createElement("img");
    img.loading = "lazy";
    img.src = `${manifest.thumb_root}/${r.t}`;
    img.alt = "";
    a.appendChild(img);
    if (r.k === "video") {
      const b = document.createElement("span");
      b.className = "video-badge";
      b.textContent = "▶ VIDEO";
      a.appendChild(b);
    }
    frag.appendChild(a);
  }
  if (matches.length > LIMIT) {
    const note = document.createElement("div");
    note.style.padding = "16px 24px";
    note.style.color = "#888";
    note.textContent = `Showing first ${LIMIT} of ${matches.length} results — refine your query.`;
    resultsGrid.appendChild(note);
  }
  resultsGrid.appendChild(frag);
}

function totalLoaded() {
  let n = 0;
  for (const rows of yearCache.values()) n += rows.length;
  return n;
}
