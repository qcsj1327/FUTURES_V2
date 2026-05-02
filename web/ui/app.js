const $ = (id) => document.getElementById(id);

function setStatus(msg) {
  const el = document.getElementById('statusLine');
  if (!el) return;
  el.textContent = msg || '';
}

const state = {
  runs: [],
  page: 0,
  limit: 20,
  selected: null,
  lastManifestJson: null,
};

function qs(params) {
  const u = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null) return;
    if (typeof v === "string" && v.trim() === "") return;
    u.set(k, String(v));
  });
  return u.toString();
}

async function apiGet(path, params = {}) {
  setStatus(`GET ${path}`);
  const url = params ? `${path}?${qs(params)}` : path;
  const r = await fetch(url);
  if (!r.ok) {
    const t = await r.text();
    setStatus(`ERR ${path}: ${r.status}`);
    throw new Error(`${r.status} ${r.statusText}: ${t}`);
  }
  const j = await r.json();
  setStatus(`OK ${path}`);
  return j;
}

function setActiveTab(name) {
  document.querySelectorAll(".tab").forEach((b) => {
    b.classList.toggle("active", b.dataset.tab === name);
  });
  document.querySelectorAll(".tabpane").forEach((p) => {
    p.classList.toggle("active", p.id === `tab-${name}`);
  });
}

function fmtBadge(approved) {
  if (approved === true) return `<span class="badge ok">approved</span>`;
  if (approved === false) return `<span class="badge no">rejected</span>`;
  return `<span class="badge">unknown</span>`;
}

function renderRuns(items) {
  const list = $("runsList");
  list.innerHTML = "";
  items.forEach((x) => {
    const card = document.createElement("div");
    card.className = "card";
    if (state.selected && x.runtime_id === state.selected) {
      card.classList.add("selected");
    }
    card.innerHTML = `
      <div class="rid">${x.runtime_id} ${fmtBadge(x.approved)}</div>
      <div class="meta">
        <div>created_at: ${x.created_at || "-"}</div>
        <div>router: ${x.router_mode_zh || x.router_mode || "-"}</div>
        <div>symbols: ${(x.universe_symbols || []).join(", ")}</div>
        <div>strategies: ${(x.strategy_names || []).join(", ")}</div>
      </div>
    `;
    card.addEventListener("click", () => selectRun(x.runtime_id));
    list.appendChild(card);
  });
}

async function loadRuns() {
  const params = {
    limit: state.limit,
    offset: state.page * state.limit,
    q: $("q").value,
    approved: $("approved").value,
    router_mode: $("router_mode").value,
    strategy: $("strategy").value,
  };
  const items = await apiGet("/runs", params);
  state.runs = items;
  renderRuns(items);
  $("pageInfo").textContent = `page=${state.page + 1} limit=${state.limit}`;

  // auto-select first item for better UX
  if (!state.selected && items.length > 0) {
    await selectRun(items[0].runtime_id);
  }
}

async function selectRun(rid) {
  state.selected = rid;
  $("selectedRid").textContent = rid;
  setStatus(`select ${rid}`);

  // highlight selection in list
  if (state.runs && state.runs.length) {
    renderRuns(state.runs);
  }

  await loadOverview().catch((e) => {
    console.error(e);
    setStatus(String(e));
  });
  setActiveTab("overview");

  // refresh active tab content after selection
  const active = document.querySelector('.tab.active');
  const tab = active ? active.dataset.tab : 'overview';
  if (tab === 'events') await loadEvents().catch((e) => { console.error(e); setStatus(String(e)); });
  if (tab === 'metrics') await loadMetrics().catch((e) => { console.error(e); setStatus(String(e)); });
  if (tab === 'manifest') await loadManifest().catch((e) => { console.error(e); setStatus(String(e)); });

}

async function loadOverview() {
  if (!state.selected) return;
  const d = await apiGet(`/runs/${state.selected}`);
  $("overview").textContent = JSON.stringify(d, null, 2);
}

async function loadMetrics() {
  if (!state.selected) return;
  const d = await apiGet(`/runs/${state.selected}/metrics`);

  const cur = d.current && d.current.summary ? d.current.summary : null;
  const cand = d.candidate && d.candidate.summary ? d.candidate.summary : null;

  const cards = document.getElementById("metricsCards");
  if (cards) {
    const kpis = [];
    if (cur) {
      kpis.push({ k: "current.success_rate", v: cur.success_rate });
      kpis.push({ k: "current.total_events", v: cur.total_events });
      kpis.push({ k: "current.max_consec_fail", v: cur.max_consecutive_failures });
      const top = cur.top_failure_reasons_zh || cur.top_failure_reasons || [];
      kpis.push({ k: "current.top_fail", v: Array.isArray(top) && top[0] ? `${top[0][0]} (${top[0][1]})` : "-" });
    }
    cards.innerHTML = kpis
      .map((x) => `<div class="kpi"><div class="k">${x.k}</div><div class="v">${x.v ?? "-"}</div></div>`)
      .join("");
  }

  $("metrics").textContent = JSON.stringify(d, null, 2);
}

async function loadManifest() {
  if (!state.selected) return;
  const d = await apiGet(`/runs/${state.selected}/manifest`);
  state.lastManifestJson = d;
  $("manifest").textContent = JSON.stringify(d, null, 2);
}

function downloadJson(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], { type: "application/json" });
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
}

async function loadEvents() {
  if (!state.selected) return;
  const params = {
    env: $("env").value,
    tail: Number($("tail").value || 200),
    since_ts: $("since_ts").value,
    event_type: $("event_type").value,
    strategy_id: $("strategy_id").value,
    success: $("success").value,
    limit: Number($("limit").value || 200),
    offset: Number($("offset").value || 0),
  };
  const d = await apiGet(`/runs/${state.selected}/events`, params);
  renderEventsTable(d.timeline || []);
}

function renderEventsTable(rows) {
  const body = $("eventsBody");
  body.innerHTML = "";
  rows.forEach((ev) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${ev.ts ?? "-"}</td>
      <td>${ev.event_type ?? "-"}</td>
      <td>${ev.symbol ?? "-"}</td>
      <td>${ev.strategy_id ?? "-"}</td>
      <td>${ev.success === true ? "true" : ev.success === false ? "false" : "-"}</td>
      <td>${ev.reason_zh ?? "-"}</td>
      <td>${ev.side_zh ?? "-"}</td>
      <td>${ev.position_side_zh ?? "-"}</td>
    `;
    body.appendChild(tr);
  });
}

function wire() {
  $("btnRefreshRuns").onclick = () => loadRuns();
  $("btnApply").onclick = () => {
    state.page = 0;
    loadRuns();
  };
  $("prevPage").onclick = () => {
    state.page = Math.max(0, state.page - 1);
    loadRuns();
  };
  $("nextPage").onclick = () => {
    state.page += 1;
    loadRuns();
  };

  document.querySelectorAll(".tab").forEach((b) => {
    b.onclick = async () => {
      setActiveTab(b.dataset.tab);
      if (b.dataset.tab === "metrics") {
        await loadMetrics().catch((e) => { console.error(e); setStatus(String(e)); });
      }
      if (b.dataset.tab === "manifest") {
        await loadManifest().catch((e) => { console.error(e); setStatus(String(e)); });
      }
      if (b.dataset.tab === "events") {
        await loadEvents().catch((e) => { console.error(e); setStatus(String(e)); });
      }
    };
  });

  $("btnLoadEvents").onclick = () => loadEvents();
  $("btnLoadManifest").onclick = () => loadManifest();
  $("btnDownloadManifest").onclick = () => {
    if (!state.lastManifestJson) return;
    downloadJson(`manifest_${state.selected}.json`, state.lastManifestJson);
  };

  // auto refresh
  setInterval(() => {
    if (!$("autoRefresh").checked) return;
    loadRuns().catch(() => {});
    if (state.selected) {
      loadOverview().catch(() => {});
    }
  }, 3000);
}

(async function main() {
  wire();
  await loadRuns();
})();
