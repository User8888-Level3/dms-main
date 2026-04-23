// Duplicate-review decision recorder.
// Decisions live in localStorage keyed by group id (gid). Each decision is one of:
//   { action: "apply", keeper_id: N, delete_ids: [...] }   — delete non-keepers
//   { action: "skip" }                                      — leave alone
// On "Export decisions.json", build a JSON blob with the full list ready for M5.

const STORAGE_KEY = "photo_index_decisions_v1";
const summaryEl = document.getElementById("decisions-summary");

let decisions = loadDecisions();
renderAll();
wire();

function loadDecisions() {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
  } catch (_) {
    return {};
  }
}

function saveDecisions() {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
  renderSummary();
}

function renderSummary() {
  const n = Object.keys(decisions).length;
  const applied = Object.values(decisions).filter(d => d.action === "apply").length;
  summaryEl.textContent = `${n} decisions · ${applied} apply`;
}

function renderAll() {
  renderSummary();
  for (const group of document.querySelectorAll(".dup-group")) {
    const gid = group.dataset.gid;
    const d = decisions[gid];
    if (!d) continue;
    applyVisual(group, d);
  }
}

function applyVisual(group, d) {
  group.classList.remove("decided-apply", "decided-skip");
  const state = group.querySelector(".decision-state");
  if (d.action === "apply") {
    group.classList.add("decided-apply");
    state.textContent = `✓ applied — delete ${d.delete_ids.length}`;
    // Mark keeper radio
    const radio = group.querySelector(`input[value="${d.keeper_id}"]`);
    if (radio) {
      radio.checked = true;
      updateKeeperClass(group);
    }
  } else if (d.action === "skip") {
    group.classList.add("decided-skip");
    state.textContent = "⊘ skipped";
  }
}

function clearDecision(group) {
  group.classList.remove("decided-apply", "decided-skip");
  group.querySelector(".decision-state").textContent = "";
}

function updateKeeperClass(group) {
  const tiles = group.querySelectorAll(".file-tile");
  tiles.forEach(t => t.classList.remove("keeper"));
  const checked = group.querySelector('input[type="radio"]:checked');
  if (checked) checked.closest(".file-tile").classList.add("keeper");
}

function wire() {
  document.addEventListener("change", e => {
    if (e.target.matches('.dup-group input[type="radio"]')) {
      const group = e.target.closest(".dup-group");
      updateKeeperClass(group);
      // Selecting a new keeper clears any prior decision
      const gid = group.dataset.gid;
      if (decisions[gid]) {
        delete decisions[gid];
        saveDecisions();
        clearDecision(group);
      }
    }
  });

  document.addEventListener("click", e => {
    const btn = e.target.closest(".decision-btn");
    if (!btn) return;
    const group = btn.closest(".dup-group");
    const gid = group.dataset.gid;
    const kind = group.dataset.kind;
    if (btn.classList.contains("apply")) {
      const checked = group.querySelector('input[type="radio"]:checked');
      if (!checked) return;
      const keeper = Number(checked.value);
      const all = Array.from(group.querySelectorAll(".file-tile"))
        .map(t => Number(t.dataset.id));
      const del = all.filter(id => id !== keeper);
      decisions[gid] = { action: "apply", kind, keeper_id: keeper, delete_ids: del };
      saveDecisions();
      applyVisual(group, decisions[gid]);
    } else if (btn.classList.contains("skip")) {
      decisions[gid] = { action: "skip", kind };
      saveDecisions();
      applyVisual(group, decisions[gid]);
    }
  });

  document.getElementById("export-btn").addEventListener("click", exportDecisions);
  document.getElementById("clear-btn").addEventListener("click", () => {
    if (!confirm("Clear all decisions? This cannot be undone.")) return;
    decisions = {};
    saveDecisions();
    document.querySelectorAll(".dup-group").forEach(clearDecision);
  });
}

function exportDecisions() {
  const payload = {
    generated_at: new Date().toISOString(),
    count: Object.keys(decisions).length,
    decisions,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `decisions-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
