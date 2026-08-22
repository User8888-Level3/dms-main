/* ============================================================
   HARV BALU — portfolio admin panel
   Vanilla ES2020, no frameworks, no build step.
   Talks to /api/admin/* (see SPEC). Optimistic UI updates;
   any failed write → toast + refresh from the server.
   Grid renders in chunks (200 tiles per animation frame) so
   2,700+ photo folders stay responsive.
   ============================================================ */
'use strict';

(() => {

  // ---------- constants ----------

  const CHUNK = 200;               // tiles appended per animation frame
  const FILTER_DEBOUNCE_MS = 120;

  // ---------- dom lookups ----------

  const $ = (sel, root) => (root || document).querySelector(sel);

  const sideStatus = $('#side-status');
  const folderList = $('#folder-list');
  const navAll = $('#nav-all');
  const navShares = $('#nav-shares');
  const allCounts = $('#all-counts');
  const sharesCountEl = $('#shares-count');

  const viewTitle = $('#view-title');
  const viewCount = $('#view-count');
  const photoTools = $('#photo-tools');
  const selCountEl = $('#sel-count');
  const filterInput = $('#filter');

  const grid = $('#grid');
  const gridEmpty = $('#grid-empty');
  const sharesView = $('#shares-view');
  const sharesBody = $('#shares-body');
  const sharesEmpty = $('#shares-empty');

  const shareDlg = $('#share-dialog');
  const shareForm = $('#share-form');
  const shareFile = $('#share-file');
  const shareDate = $('#share-date');
  const shareNote = $('#share-note');
  const shareCreate = $('#share-create');
  const shareResult = $('#share-result');
  const shareUrlInput = $('#share-url');
  const shareExpiryLine = $('#share-expiry-line');

  const toastEl = $('#toast');

  const tileTpl = $('#tile-tpl');
  const folderTpl = $('#folder-tpl');
  const shareRowTpl = $('#share-row-tpl');

  // ---------- state ----------

  let folders = [];              // [{folder, total, public, artwork, cover_sha1}]
  let sharesTotal = 0;           // count shown in the sidebar
  let curView = 'photos';        // 'photos' | 'shares'
  let curFolder = null;          // null = All
  let photos = [];               // current view's photo rows
  let photoById = new Map();     // id -> photo row
  let curList = [];              // photos after the filename filter
  let shares = [];               // rows for the Shares view
  let selected = new Set();      // selected photo ids
  let tileById = new Map();      // id -> rendered tile element
  let filterText = '';
  let renderGen = 0;             // cancels stale chunked renders
  let shareTargetId = null;      // photo id the dialog is minting a link for

  // ---------- helpers ----------

  async function api(path, opts) {
    const res = await fetch(path, opts);
    let data = null;
    try { data = await res.json(); } catch (_err) { /* non-JSON error body */ }
    if (!res.ok || (data && data.error)) {
      throw new Error((data && data.error) || ('HTTP ' + res.status));
    }
    return data || {};
  }

  function post(path, body) {
    return api(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  function fmtDate(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
  }

  function fmtDateTime(iso) {
    if (!iso) return '—';
    const d = new Date(iso);
    if (Number.isNaN(d.getTime())) return iso;
    return d.toLocaleString(undefined, {
      month: 'short', day: 'numeric', year: 'numeric',
      hour: 'numeric', minute: '2-digit',
    });
  }

  function plural(n, word) { return n + ' ' + word + (n === 1 ? '' : 's'); }

  let toastTimer = 0;
  function toast(msg, isError) {
    toastEl.textContent = msg;
    toastEl.classList.toggle('toast--error', !!isError);
    toastEl.hidden = false;
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { toastEl.hidden = true; }, isError ? 4200 : 2400);
  }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      toast('Copied to clipboard');
    } catch (_err) {
      toast('Copy failed — select the link and copy manually', true);
    }
  }

  function shareUrlOf(s) {
    return s.url || (location.origin + '/s/' + s.token);
  }

  // A failed write: tell the admin, then re-pull truth from the server.
  function failAndRefresh(err) {
    toast('Failed: ' + err.message, true);
    refreshCurrent();
    refreshState();
  }

  // ---------- sidebar ----------

  async function loadState() {
    const d = await api('/api/admin/state');
    folders = d.folders || [];
    sharesTotal = d.shares || 0;
    renderSidebar();
  }

  async function refreshState() {
    try { await loadState(); } catch (_err) { /* keep the stale sidebar */ }
  }

  function renderSidebar() {
    folderList.textContent = '';
    const frag = document.createDocumentFragment();
    let tot = 0;
    let pub = 0;
    for (const f of folders) {
      tot += f.total;
      pub += f.public;
      const li = folderTpl.content.firstElementChild.cloneNode(true);
      const btn = $('.adm-folder', li);
      btn.dataset.folder = f.folder;
      $('.adm-folder__name', li).textContent = f.folder;
      $('.adm-folder__art', li).hidden = !(f.artwork > 0);
      $('.adm-folder__counts', li).textContent = f.public + '/' + f.total;
      frag.appendChild(li);
    }
    folderList.appendChild(frag);
    allCounts.textContent = pub + '/' + tot;
    sharesCountEl.textContent = String(sharesTotal);
    sideStatus.hidden = true;
    markActive();
  }

  function markActive() {
    document.querySelectorAll('.adm-folder').forEach((b) => b.classList.remove('is-active'));
    if (curView === 'shares') {
      navShares.classList.add('is-active');
    } else if (!curFolder) {
      navAll.classList.add('is-active');
    } else {
      const btn = document.querySelector(`.adm-folder[data-folder="${CSS.escape(curFolder)}"]`);
      if (btn) btn.classList.add('is-active');
    }
  }

  // ---------- view switching ----------

  function showView(name) {
    const photosMode = name === 'photos';
    grid.hidden = !photosMode;
    gridEmpty.hidden = true;
    sharesView.hidden = photosMode;
    photoTools.hidden = !photosMode;
    filterInput.placeholder = photosMode ? 'Filter filename…' : 'Filter links…';
  }

  function resetFilter() {
    filterInput.value = '';
    filterText = '';
  }

  async function openPhotos(folder) {
    curView = 'photos';
    curFolder = folder;
    selected.clear();
    updateSelCount();
    resetFilter();
    showView('photos');
    viewTitle.textContent = folder || 'All';
    viewCount.textContent = 'Loading…';
    markActive();

    let data;
    try {
      data = folder
        ? await api('/api/admin/photos?folder=' + encodeURIComponent(folder))
        : await fetchAllPhotos();
    } catch (err) {
      toast('Load failed: ' + err.message, true);
      photos = [];
      photoById = new Map();
      curList = [];
      renderGrid([]);
      viewCount.textContent = 'Load failed';
      return;
    }
    photos = data.photos || [];
    photoById = new Map(photos.map((p) => [p.id, p]));
    applyFilter();
  }

  async function fetchAllPhotos() {
    try {
      return await api('/api/admin/photos');
    } catch (_err) {
      // Fallback if the server insists on ?folder= — merge every folder.
      const merged = [];
      for (const f of folders) {
        const d = await api('/api/admin/photos?folder=' + encodeURIComponent(f.folder));
        merged.push(...(d.photos || []));
      }
      merged.sort((a, b) => String(a.taken_at || '~') < String(b.taken_at || '~') ? -1 : 1);
      return { photos: merged };
    }
  }

  async function openShares() {
    curView = 'shares';
    curFolder = null;
    selected.clear();
    updateSelCount();
    resetFilter();
    showView('shares');
    viewTitle.textContent = 'Shares';
    viewCount.textContent = 'Loading…';
    markActive();

    try {
      const d = await api('/api/admin/shares');
      shares = d.shares || [];
    } catch (err) {
      toast('Load failed: ' + err.message, true);
      shares = [];
    }
    sharesTotal = shares.length;
    sharesCountEl.textContent = String(sharesTotal);
    renderShares();
  }

  function refreshCurrent() {
    if (curView === 'shares') openShares();
    else openPhotos(curFolder);
  }

  // ---------- filtering ----------

  function applyFilter() {
    const q = filterText.trim().toLowerCase();
    if (curView === 'shares') {
      renderShares();
      return;
    }
    curList = q ? photos.filter((p) => p.filename.toLowerCase().includes(q)) : photos.slice();
    renderGrid(curList);
    updateCountLine();
  }

  function updateCountLine() {
    if (curView !== 'photos') return;
    const pub = photos.reduce((n, p) => n + (p.visibility === 'public' ? 1 : 0), 0);
    let line = plural(photos.length, 'photo') + ' · ' + pub + ' public';
    if (filterText.trim()) line += ' · ' + curList.length + ' shown';
    viewCount.textContent = line;
  }

  // ---------- photo grid (chunked render) ----------

  function renderGrid(list) {
    const gen = ++renderGen;
    grid.textContent = '';
    tileById = new Map();
    gridEmpty.hidden = list.length > 0;
    gridEmpty.textContent = photos.length
      ? 'No photos match this filter.'
      : 'No photos in this view.';

    let i = 0;
    const step = () => {
      if (gen !== renderGen) return;      // a newer render started — abandon
      const frag = document.createDocumentFragment();
      const end = Math.min(i + CHUNK, list.length);
      for (; i < end; i++) frag.appendChild(buildTile(list[i]));
      grid.appendChild(frag);
      if (i < list.length) requestAnimationFrame(step);
    };
    step();
  }

  function buildTile(p) {
    const node = tileTpl.content.firstElementChild.cloneNode(true);
    node.dataset.id = String(p.id);
    node.dataset.sha1 = p.sha1;
    const img = $('.ph-tile__img', node);
    img.src = '/media/thumb/' + p.sha1 + '.jpg';
    img.alt = p.filename;
    $('.ph-tile__name', node).textContent = p.filename;
    const check = $('.ph-tile__check', node);
    check.checked = selected.has(p.id);
    check.setAttribute('aria-label', 'Select ' + p.filename);
    if (selected.has(p.id)) node.classList.add('is-selected');
    patchTileNode(node, p);
    tileById.set(p.id, node);
    return node;
  }

  function patchTileNode(node, p) {
    $('.chip--public', node).hidden = p.visibility !== 'public';
    $('.chip--private', node).hidden = p.visibility === 'public';
    $('.ph-tile__art', node).hidden = !p.is_artwork;
    $('.ph-tile__video', node).hidden = p.kind !== 'video';
  }

  function patchTile(p) {
    const node = tileById.get(p.id);
    if (node) patchTileNode(node, p);
  }

  // ---------- selection ----------

  function updateSelCount() {
    selCountEl.textContent = selected.size ? selected.size + ' selected' : '';
  }

  function setSelect(id, on) {
    if (on) selected.add(id);
    else selected.delete(id);
    const node = tileById.get(id);
    if (node) {
      node.classList.toggle('is-selected', on);
      $('.ph-tile__check', node).checked = on;
    }
    updateSelCount();
  }

  function toggleSelect(id) {
    setSelect(id, !selected.has(id));
  }

  function syncSelectionDom() {
    for (const [id, node] of tileById) {
      const on = selected.has(id);
      node.classList.toggle('is-selected', on);
      $('.ph-tile__check', node).checked = on;
    }
    updateSelCount();
  }

  // ---------- bulk actions ----------

  async function applyVisibility(vis) {
    const ids = [...selected];

    if (!ids.length) {
      // No selection: offer the folder-wide toggle when a folder is open.
      if (!curFolder) {
        toast('Select photos first', true);
        return;
      }
      const msg = 'No photos selected — make ALL ' + photos.length +
        ' photos in “' + curFolder + '” ' + vis + '?';
      if (!confirm(msg)) return;
      photos.forEach((p) => { p.visibility = vis; patchTile(p); });
      updateCountLine();
      try {
        const r = await post('/api/admin/visibility', { folder: curFolder, visibility: vis });
        toast(plural(r.changed, 'photo') + ' made ' + vis);
        refreshState();
      } catch (err) { failAndRefresh(err); }
      return;
    }

    ids.forEach((id) => {
      const p = photoById.get(id);
      if (p) { p.visibility = vis; patchTile(p); }
    });
    updateCountLine();
    try {
      const r = await post('/api/admin/visibility', { ids, visibility: vis });
      toast(plural(r.changed, 'photo') + ' made ' + vis);
      refreshState();
    } catch (err) { failAndRefresh(err); }
  }

  async function applyArtwork() {
    const ids = [...selected];
    if (!ids.length) {
      toast('Select photos first', true);
      return;
    }
    // Toggle: if every selected photo is already artwork, unmark; else mark.
    const flag = !ids.every((id) => {
      const p = photoById.get(id);
      return p && p.is_artwork;
    });
    ids.forEach((id) => {
      const p = photoById.get(id);
      if (p) { p.is_artwork = flag ? 1 : 0; patchTile(p); }
    });
    try {
      await post('/api/admin/artwork', { ids, artwork: flag });
      toast(plural(ids.length, 'photo') + (flag ? ' marked artwork ✦' : ' unmarked artwork'));
      refreshState();
    } catch (err) { failAndRefresh(err); }
  }

  // ---------- share dialog ----------

  function openShareDialog(id) {
    const p = photoById.get(id);
    if (!p) return;
    shareTargetId = id;
    shareFile.textContent = p.filename;
    shareForm.hidden = false;
    shareResult.hidden = true;
    shareForm.reset();               // radios back to the 7-day default
    shareDate.disabled = true;
    shareDate.value = '';
    shareDlg.showModal();
  }

  async function createShare(ev) {
    ev.preventDefault();
    const choice = shareForm.elements.expires.value;
    let expires = choice;
    if (choice === 'custom') {
      if (!shareDate.value) {
        toast('Pick a custom date first', true);
        shareDate.focus();
        return;
      }
      expires = shareDate.value;     // YYYY-MM-DD
    }
    const body = { photo_id: shareTargetId, expires };
    const note = shareNote.value.trim();
    if (note) body.note = note;

    shareCreate.disabled = true;
    try {
      const r = await post('/api/admin/share', body);
      shareUrlInput.value = r.url;
      shareExpiryLine.textContent = r.expires_at
        ? 'expires ' + fmtDateTime(r.expires_at)
        : 'permanent link';
      shareForm.hidden = true;
      shareResult.hidden = false;
      shareUrlInput.focus();
      shareUrlInput.select();
      sharesTotal += 1;
      sharesCountEl.textContent = String(sharesTotal);
      toast('Share link created');
    } catch (err) {
      toast('Failed: ' + err.message, true);
    } finally {
      shareCreate.disabled = false;
    }
  }

  // ---------- shares view ----------

  function shareStatus(s) {
    if (s.revoked) return 'REVOKED';
    if (s.expired) return 'EXPIRED';
    if (s.expires_at && new Date(s.expires_at) <= new Date()) return 'EXPIRED';
    return 'ACTIVE';
  }

  function renderShares() {
    const q = filterText.trim().toLowerCase();
    const list = q
      ? shares.filter((s) => (s.filename || '').toLowerCase().includes(q))
      : shares;

    sharesBody.textContent = '';
    const frag = document.createDocumentFragment();
    for (const s of list) frag.appendChild(buildShareRow(s));
    sharesBody.appendChild(frag);

    sharesEmpty.hidden = list.length > 0;
    sharesEmpty.textContent = shares.length
      ? 'No links match this filter.'
      : 'No share links yet. Hover a photo and hit ⤴ Share.';

    let line = plural(shares.length, 'link');
    if (q) line += ' · ' + list.length + ' shown';
    viewCount.textContent = line;
  }

  function buildShareRow(s) {
    const row = shareRowTpl.content.firstElementChild.cloneNode(true);
    row.dataset.token = s.token;

    const thumb = $('.share-row__thumb', row);
    thumb.src = '/media/thumb/' + s.sha1 + '.jpg';
    thumb.alt = s.filename || '';

    $('.share-row__file', row).textContent = s.filename || '—';
    const noteEl = $('.share-row__note', row);
    if (s.note) noteEl.textContent = s.note;
    else noteEl.hidden = true;

    $('.share-row__created', row).textContent = fmtDateTime(s.created_at);
    $('.share-row__expires', row).textContent = s.expires_at ? fmtDateTime(s.expires_at) : 'Never';

    const status = shareStatus(s);
    const chip = $('.chip--status', row);
    chip.textContent = status;
    chip.classList.add('chip--' + status.toLowerCase());
    if (status === 'REVOKED') row.classList.add('share-row--revoked');
    if (status !== 'ACTIVE') $('.share-row__revoke', row).hidden = true;

    return row;
  }

  async function revokeShare(s) {
    const msg = 'Revoke this link for “' + (s.filename || s.token) +
      '”? It stops working immediately.';
    if (!confirm(msg)) return;
    s.revoked = 1;                    // optimistic
    renderShares();
    try {
      await post('/api/admin/revoke', { token: s.token });
      toast('Link revoked');
    } catch (err) {
      toast('Failed: ' + err.message, true);
      openShares();                   // re-pull truth
    }
  }

  // ---------- events ----------

  function bindEvents() {
    // Sidebar
    navAll.addEventListener('click', () => openPhotos(null));
    navShares.addEventListener('click', () => openShares());
    folderList.addEventListener('click', (e) => {
      const btn = e.target.closest('.adm-folder');
      if (btn) openPhotos(btn.dataset.folder);
    });

    // Toolbar
    $('#sel-all').addEventListener('click', () => {
      curList.forEach((p) => selected.add(p.id));
      syncSelectionDom();
    });
    $('#sel-none').addEventListener('click', () => {
      selected.clear();
      syncSelectionDom();
    });
    $('#btn-public').addEventListener('click', () => applyVisibility('public'));
    $('#btn-private').addEventListener('click', () => applyVisibility('private'));
    $('#btn-artwork').addEventListener('click', () => applyArtwork());
    $('#btn-share').addEventListener('click', () => {
      if (selected.size !== 1) {
        toast('Select exactly one photo to share', true);
        return;
      }
      openShareDialog([...selected][0]);
    });

    // Filename filter (debounced, client-side)
    let filterTimer = 0;
    filterInput.addEventListener('input', () => {
      clearTimeout(filterTimer);
      filterTimer = setTimeout(() => {
        filterText = filterInput.value;
        applyFilter();
      }, FILTER_DEBOUNCE_MS);
    });

    // Grid: click = toggle check · alt-click = open display · ⤴ = share
    grid.addEventListener('click', (e) => {
      const tile = e.target.closest('.ph-tile');
      if (!tile) return;
      const id = Number(tile.dataset.id);
      if (e.target.closest('.ph-tile__share')) {
        openShareDialog(id);
        return;
      }
      if (e.target.classList.contains('ph-tile__check')) return;  // change handler owns it
      if (e.altKey) {
        window.open('/media/display/' + tile.dataset.sha1 + '.jpg', '_blank');
        return;
      }
      toggleSelect(id);
    });
    grid.addEventListener('change', (e) => {
      if (!e.target.classList.contains('ph-tile__check')) return;
      const tile = e.target.closest('.ph-tile');
      if (tile) setSelect(Number(tile.dataset.id), e.target.checked);
    });

    // Share dialog
    shareForm.addEventListener('submit', createShare);
    shareForm.addEventListener('change', () => {
      shareDate.disabled = shareForm.elements.expires.value !== 'custom';
      if (!shareDate.disabled) shareDate.focus();
    });
    $('#share-cancel').addEventListener('click', () => shareDlg.close());
    $('#share-close').addEventListener('click', () => shareDlg.close());
    $('#share-done').addEventListener('click', () => shareDlg.close());
    $('#share-copy').addEventListener('click', () => copyText(shareUrlInput.value));
    shareUrlInput.addEventListener('focus', () => shareUrlInput.select());

    // Shares table: copy / revoke
    sharesBody.addEventListener('click', (e) => {
      const copyBtn = e.target.closest('.share-row__copy');
      const revokeBtn = e.target.closest('.share-row__revoke');
      if (!copyBtn && !revokeBtn) return;
      const row = e.target.closest('.share-row');
      const s = shares.find((x) => x.token === row.dataset.token);
      if (!s) return;
      if (copyBtn) copyText(shareUrlOf(s));
      else revokeShare(s);
    });
  }

  // ---------- init ----------

  async function init() {
    bindEvents();
    try {
      await loadState();
    } catch (err) {
      sideStatus.textContent = 'Failed to load: ' + err.message;
      viewCount.textContent = 'Load failed';
      toast('Failed to load admin state: ' + err.message, true);
      return;
    }
    openPhotos(null);
  }

  init();

})();
