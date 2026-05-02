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
  selectedEvent: null,
  lastManifestJson: null,
  lastEventsUrl: null,
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

function parseIso(s) {
  if (!s) return null;
  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function escapeHtml(s) {
  return String(s)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function highlight(s, q) {
  const text = String(s ?? '');
  const query = String(q ?? '').trim();
  if (!query) return escapeHtml(text);
  const re = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
  return escapeHtml(text).replace(re, (m) => `<span class="hltext">${m}</span>`);
}

function fmtBadge(approved) {
  if (approved === true) return `<span class="badge ok">approved</span>`;
  if (approved === false) return `<span class="badge no">rejected</span>`;
  return `<span class="badge">unknown</span>`;
}

function renderRuns(items) {
  const list = $("runsList");
  list.innerHTML = "";

  const q = $("q") ? $("q").value : "";
  const recent = $("recentHours") ? $("recentHours").value : "";
  let filtered = items.slice();

  if (recent) {
    const hrs = Number(recent);
    const now = Date.now();
    filtered = filtered.filter((x) => {
      const d = parseIso(x.created_at);
      if (!d) return true;
      return now - d.getTime() <= hrs * 3600 * 1000;
    });
  }

    if (filtered.length === 0) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = `<div class="rid">无结果</div><div class="meta"><div>请放宽筛选条件（q/approved/router/strategy/最近N小时）</div></div>`;
    list.appendChild(card);
    return;
  }

filtered.forEach((x) => {
    const card = document.createElement("div");
    card.className = "card";
    if (state.selected && x.runtime_id === state.selected) {
      card.classList.add("selected");
    }

    const ridHtml = highlight(x.runtime_id, q);
    const routerHtml = highlight(x.router_mode_zh || x.router_mode || "-", q);
    const stratHtml = highlight((x.strategy_names || []).join(", "), q);

    card.innerHTML = `
      <div class="rid">${ridHtml} ${fmtBadge(x.approved)}</div>
      <div class="meta">
        <div>created_at: ${escapeHtml(x.created_at || "-")}</div>
        <div>router: ${routerHtml}</div>
        <div>symbols: ${escapeHtml((x.universe_symbols || []).join(", "))}</div>
        <div>strategies: ${stratHtml}</div>
        <div style="margin-top:6px;">
          <button class="btn small js-copy-link">复制链接</button>
        </div>
      </div>
    `;

    card.addEventListener("click", (e) => {
      const btn = e.target && e.target.closest ? e.target.closest(".js-copy-link") : null;
      if (btn) return; // handled separately
      selectRun(x.runtime_id);
    });

    const btn = card.querySelector(".js-copy-link");
    if (btn) {
      btn.addEventListener("click", async (e) => {
        e.stopPropagation();
        const url = `${location.origin}/ui#rid=${encodeURIComponent(x.runtime_id)}`;
        await copyText(url);
      });
    }

    list.appendChild(card);
  });
}

function getRidFromHash() {
  const h = (location.hash || '').trim();
  const m = h.match(/rid=([^&]+)/);
  return m ? decodeURIComponent(m[1]) : null;
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

  const hashRid = getRidFromHash();
  if (hashRid && !items.some((x) => x.runtime_id === hashRid)) {
    setStatus(`hash rid not found: ${hashRid}`);
  }

  if (hashRid && items.some((x) => x.runtime_id === hashRid)) {
    if (state.selected !== hashRid) await selectRun(hashRid);
  } else if (!state.selected && items.length > 0) {
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
  setJson($('overview'), d, { collapseDepth: 0 });
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

  setJson($('metrics'), d, { collapseDepth: 0 });
}

async function loadManifest() {
  if (!state.selected) return;
  const d = await apiGet(`/runs/${state.selected}/manifest`);
  state.lastManifestJson = d;
  setJson($('manifest'), d, { collapseDepth: 0 });
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    setStatus('copied');
  } catch (e) {
    console.error(e);
    setStatus('copy failed');
  }
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
  const url = `/runs/${state.selected}/events?${qs(params)}`;
  state.lastEventsUrl = url;
  const d = await apiGet(`/runs/${state.selected}/events`, params);
  renderEventsTable(d.timeline || []);
}

function applyEventsFilter({ since_ts, event_type, strategy_id, success }) {
  if (since_ts !== undefined && since_ts !== null) {
    $("since_ts").value = String(since_ts);
  }
  if (event_type !== undefined && event_type !== null) {
    $("event_type").value = String(event_type);
  }
  if (strategy_id !== undefined && strategy_id !== null) {
    $("strategy_id").value = String(strategy_id);
  }
  if (success !== undefined && success !== null) {
    $("success").value = String(success);
  }
  // reset paging
  $("offset").value = "0";
  loadEvents();
}

function renderEventsTable(rows) {
  const body = $("eventsBody");
  body.innerHTML = "";
  rows.forEach((ev) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><span class="linklike" data-k="since_ts">${ev.ts ?? "-"}</span></td>
      <td><span class="linklike" data-k="event_type">${ev.event_type ?? "-"}</span></td>
      <td>${ev.symbol ?? "-"}</td>
      <td><span class="linklike" data-k="strategy_id">${ev.strategy_id ?? "-"}</span></td>
      <td><span class="linklike" data-k="success">${ev.success === true ? "true" : ev.success === false ? "false" : "-"}</span></td>
      <td>${ev.reason_zh ?? "-"}</td>
      <td>${ev.side_zh ?? "-"}</td>
      <td>${ev.position_side_zh ?? "-"}</td>
    `;

    tr.addEventListener("click", () => {
      // highlight
      document.querySelectorAll("#eventsBody tr").forEach((x) => x.classList.remove("selected"));
      tr.classList.add("selected");

      state.selectedEvent = ev;

      // cell quick filters
      tr.querySelectorAll('.linklike').forEach((sp) => {
        sp.addEventListener('click', (e) => {
          e.stopPropagation();
          const k = sp.getAttribute('data-k');
          const v = sp.textContent || '';
          if (k === 'since_ts' && v !== '-' ) applyEventsFilter({ since_ts: v });
          if (k === 'event_type' && v !== '-' ) applyEventsFilter({ event_type: v });
          if (k === 'strategy_id' && v !== '-' ) applyEventsFilter({ strategy_id: v });
          if (k === 'success' && (v === 'true' || v === 'false')) applyEventsFilter({ success: v });
        });
      });

      const pre = $("eventDetail");
      if (pre) {
        pre.style.display = "block";
        setJson(pre, ev, { collapseDepth: 0 });
      }
    });

    body.appendChild(tr);
  });
}

function wire() {
  $("btnRefreshRuns").onclick = () => loadRuns();
  const rh = $("recentHours");
  if (rh) rh.addEventListener('change', () => loadRuns());

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
  const btnPrevEvents = $("btnPrevEvents");
  if (btnPrevEvents) {
    btnPrevEvents.onclick = () => {
      const cur = Number($("offset").value || 0);
      const lim = Number($("limit").value || 200);
      $("offset").value = String(Math.max(0, cur - lim));
      loadEvents();
    };
  }
  const btnNextEvents = $("btnNextEvents");
  if (btnNextEvents) {
    btnNextEvents.onclick = () => {
      const cur = Number($("offset").value || 0);
      const lim = Number($("limit").value || 200);
      $("offset").value = String(cur + lim);
      loadEvents();
    };
  }

  $("btnLoadManifest").onclick = () => loadManifest();
  const btnCopyEvent = $("btnCopyEvent");
  if (btnCopyEvent) {
    btnCopyEvent.onclick = () => {
      if (!state.selectedEvent) return;
      copyText(JSON.stringify(state.selectedEvent, null, 2));
    };
  }
  const btnCopyEventsLink = $("btnCopyEventsLink");
  if (btnCopyEventsLink) {
    btnCopyEventsLink.onclick = () => {
      if (!state.lastEventsUrl) return;
      const full = `${location.origin}${state.lastEventsUrl}`;
      copyText(full);
    };
  }

  $("btnDownloadManifest").onclick = () => {
    if (!state.lastManifestJson) return;
    downloadJson(`manifest_${state.selected}.json`, state.lastManifestJson);
  };

  // json toolbars
  document.querySelectorAll('.jsonbar').forEach((bar) => {
    const targetId = bar.getAttribute('data-target');
    const target = targetId ? document.getElementById(targetId) : null;
    const btnExp = bar.querySelector('.js-expand');
    const btnCol = bar.querySelector('.js-collapse');
    const input = bar.querySelector('.jsonsearch');
    if (btnExp) btnExp.addEventListener('click', () => setAllDetailsOpen(target, true));
    if (btnCol) btnCol.addEventListener('click', () => setAllDetailsOpen(target, false));
    if (input) input.addEventListener('input', () => highlightText(target, input.value));
  });

  // auto refresh
  setInterval(() => {
    if (!$("autoRefresh").checked) return;
    loadRuns().catch(() => {});
    if (state.selected) {
      loadOverview().catch(() => {});
    }
  }, 3000);
}


function isPlainObject(x) {
  return x && typeof x === "object" && !Array.isArray(x);
}

function renderJsonTree(obj, { collapseDepth = 0 } = {}) {
  const root = document.createElement("div");

  function makeNode(value, key, depth) {
    const isObj = isPlainObject(value);
    const isArr = Array.isArray(value);

    if (isObj || isArr) {
      const details = document.createElement("details");
      if (depth < collapseDepth) details.open = true;

      const summary = document.createElement("summary");
      const label = key !== null ? `${key}: ` : "";
      const size = isArr ? `Array(${value.length})` : `Object(${Object.keys(value).length})`;
      summary.textContent = label + size;
      details.appendChild(summary);

      const entries = isArr ? value.map((v, i) => [String(i), v]) : Object.entries(value);
      for (const [k, v] of entries) {
        details.appendChild(makeNode(v, k, depth + 1));
      }
      return details;
    }

    const line = document.createElement("div");
    line.className = "kv leaf";
    const kEl = document.createElement("div");
    kEl.className = "k";
    kEl.textContent = key !== null ? `${key}` : "";
    const vEl = document.createElement("div");
    vEl.className = "v";
    if (typeof value === "string") vEl.textContent = JSON.stringify(value);
    else vEl.textContent = String(value);
    line.appendChild(kEl);
    line.appendChild(vEl);
    return line;
  }

  root.appendChild(makeNode(obj, null, 0));
  return root;
}

function setAllDetailsOpen(container, open) {
  if (!container) return;
  container.querySelectorAll('details').forEach((d) => { d.open = !!open; });
}

function clearHighlights(container) {
  if (!container) return;
  container.querySelectorAll('mark.hl').forEach((m) => {
    const text = document.createTextNode(m.textContent || '');
    m.replaceWith(text);
  });
}

function highlightText(container, q) {
  if (!container) return;
  clearHighlights(container);
  const query = (q || '').trim();
  if (!query) return;
  const re = new RegExp(query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'ig');
  container.querySelectorAll('.k, .v').forEach((node) => {
    const s = node.textContent || '';
    if (!re.test(s)) return;
    const parts = s.split(re);
    const matches = s.match(re) || [];
    node.textContent = '';
    for (let i = 0; i < parts.length; i++) {
      node.appendChild(document.createTextNode(parts[i]));
      if (i < matches.length) {
        const mk = document.createElement('mark');
        mk.className = 'hl';
        mk.textContent = matches[i];
        node.appendChild(mk);
      }
    }
  });
}

function setJson(el, obj, opts) {
  if (!el) return;
  el.innerHTML = "";
  el.appendChild(renderJsonTree(obj, opts));
}

(async function main() {
  wire();
  await loadRuns();
})();
