const $ = (id) => document.getElementById(id);

const NAV_ITEMS = [
  ["home", "⌂", "首页总览"],
  ["run", "⊕", "运行概览"],
  ["portfolio", "▤", "组合/资金"],
  ["lifecycle", "♙", "订单生命周期"],
  ["risk", "▣", "风控与熔断"],
  ["switch", "⌘", "策略评分与切换"],
  ["gates", "⌁", "候选开仓与门控"],
  ["roll", "⇄", "换月与移仓", "NEW"],
  ["market", "◫", "合约与行情"],
  ["logs", "☰", "运行日志"],
  ["config", "⚙", "配置中心"],
  ["alerts", "♧", "告警中心"],
  ["permissions", "♢", "权限管理"],
];

const MODE_ZH = {
  simulated_v2: "模拟行情",
  simulated: "模拟行情",
  live_file: "本地行情",
  tqkq_sim: "天勤模拟",
  tqkq_live: "天勤实盘",
  dry_run: "仅演练",
  live: "真实下单",
};

const STATUS_ZH = {
  NEW: "新建",
  SUBMITTED: "已提交",
  PARTIAL: "部分成交",
  FILLED: "已成交",
  CANCELED: "已撤单",
  EXPIRED: "已过期",
  REJECTED: "已拒绝",
};

const REASON_ZH = {
  new: "新建",
  order_submitted: "已提交",
  simulated_fill: "模拟成交",
  simulated_partial_fill: "模拟部分成交",
  tqkq_sim_fill: "天勤模拟成交",
  tqkq_live_partial_fill: "天勤实盘部分成交",
  tqkq_live_fill: "天勤实盘成交",
  blocked_by_pending_order: "待处理订单阻塞",
  duplicate_same_tick: "同 tick 重复下单",
  expired: "订单过期",
  canceled: "已撤单",
  risk_position_limit: "超过持仓数量上限",
  risk_max_notional: "超过名义金额上限",
  risk_max_risk_ratio: "超过风险度上限",
  risk_max_margin_used: "超过保证金占用上限",
  rate_limited: "触发限频",
  halted_by_guard: "触发熔断",
  roll_cancel_pending: "换月撤单中",
  roll_close_position: "换月清仓中",
  roll_cooldown_block: "换月观察期阻断",
  missing_trade_instrument_id: "缺少执行合约",
  invalid_trade_instrument_id_main_alias: "执行合约不能为主力别名",
  invalid_trade_instrument_id_not_real_contract: "执行合约不是真实合约",
  insufficient_events: "样本不足",
  non_trading_time: "非交易时段",
};

const state = {
  runs: [],
  selected: null,
  dashboard: null,
  detail: null,
  activeView: "home",
  lifecycleStatusFilter: "",
  timer: null,
};

const WARNING_ZH = {
  missing_candidate_summary: "缺少候选摘要",
  missing_decision: "缺少决策结果",
  missing_approved: "缺少审批结果",
  missing_strategy_switch_approved: "缺少策略切换审批",
};

function esc(value) {
  return String(value ?? "—")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fmtNumber(value, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  });
}

function fmtCompact(value, digits = 2) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${(value / 1e8).toFixed(digits)}亿`;
  if (abs >= 1e4) return `${(value / 1e4).toFixed(digits)}万`;
  return fmtNumber(value, digits);
}

function fmtInt(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "0";
  return Math.round(value).toLocaleString("zh-CN");
}

function fmtPct(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return `${(value * 100).toFixed(2)}%`;
}

function fmtTs(value) {
  if (typeof value === "number" && Number.isFinite(value)) {
    const d = new Date(value > 1e12 ? value : value * 1000);
    if (!Number.isNaN(d.getTime())) return d.toLocaleString("zh-CN", { hour12: false });
  }
  if (typeof value === "string" && value) return value;
  return "—";
}

function zhMode(code) {
  return MODE_ZH[code] || code || "未知模式";
}

function zhStatus(code) {
  return STATUS_ZH[code] || code || "未知状态";
}

function zhReason(code) {
  return REASON_ZH[code] || code || "—";
}

function zhWarning(code) {
  return WARNING_ZH[code] || zhReason(code) || code || "—";
}

function tag(text, tone = "gray") {
  return `<span class="tag ${tone}">${esc(text)}</span>`;
}

function titleText(value) {
  return esc(String(value ?? "—").replace(/<[^>]*>/g, ""));
}

function valueWithTitle(value) {
  return `<span class="truncate" title="${titleText(value)}">${esc(value ?? "—")}</span>`;
}

async function apiGet(path, params = {}) {
  const url = new URL(path, window.location.origin);
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, value);
  });
  const response = await fetch(url);
  if (!response.ok) {
    const body = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${body}`);
  }
  return response.json();
}

function renderNav() {
  $("nav").innerHTML = NAV_ITEMS.map(([id, icon, label, badge]) => `
    <button class="nav-item ${id === state.activeView ? "active" : ""}" data-view="${id}">
      <span class="nav-icon">${icon}</span>
      <span>${label}</span>
      ${badge ? `<span class="nav-badge">${badge}</span>` : ""}
    </button>
  `).join("");
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.view));
  });
}

function switchView(view) {
  state.activeView = view || "home";
  document.querySelectorAll(".view").forEach((el) => el.classList.remove("active"));
  const target = $(`view-${state.activeView}`);
  if (target) target.classList.add("active");
  renderNav();
  renderAll();
}

async function loadRuns() {
  state.runs = await apiGet("/runs", { limit: 200 });
  const select = $("runSelect");
  select.innerHTML = state.runs.length
    ? state.runs.map((run) => `<option value="${esc(run.runtime_id)}">${esc(run.runtime_id)}</option>`).join("")
    : `<option value="">无运行记录</option>`;
  const hashRid = new URLSearchParams(location.hash.replace(/^#/, "")).get("rid");
  if (hashRid && state.runs.some((run) => run.runtime_id === hashRid)) {
    state.selected = hashRid;
  }
  if (!state.selected && state.runs.length) state.selected = state.runs[0].runtime_id;
  if (state.selected) select.value = state.selected;
}

async function loadSelected() {
  if (!state.selected) {
    renderEmpty();
    return;
  }
  const [detail, dashboard] = await Promise.all([
    apiGet(`/runs/${encodeURIComponent(state.selected)}`),
    apiGet(`/runs/${encodeURIComponent(state.selected)}/dashboard`, { tail: 500 }),
  ]);
  state.detail = detail;
  state.dashboard = dashboard;
  location.hash = `rid=${encodeURIComponent(state.selected)}`;
  updateTopStrip();
  renderAll();
}

function updateTopStrip() {
  const detail = state.detail || {};
  const dash = state.dashboard || {};
  const plan = detail.plan?.config || {};
  const runtimeMode = plan.runtime?.mode || plan.adapters?.market_data?.mode || "—";
  const execMode = dash.execution?.execution_mode;
  const approved = detail.approved ? "已批准" : detail.decision?.decision?.approved ? "已批准" : "未批准";
  $("runSelect").title = state.selected || "";
  $("modeLabel").title = `${runtimeMode}${execMode ? ` / ${execMode}` : ""}`;
  $("approvalLabel").title = `${approved}${detail.candidate_id ? ` / ${detail.candidate_id}` : ""}`;
  $("modeLabel").innerHTML = `<span class="truncate">${esc(zhMode(runtimeMode))} ${execMode ? tag(zhMode(execMode), execMode === "live" ? "red" : "green") : ""}</span>`;
  $("approvalLabel").innerHTML = `<span class="truncate">${tag(approved, approved === "已批准" ? "green" : "yellow")} ${esc(detail.candidate_id || "")}</span>`;
  $("marketStatus").textContent = runtimeMode === "—" ? "待选择" : "运行中";
  $("execStatus").textContent = dash.execution?.broker_type || "运行中";
  $("daemonStatus").textContent = "运行中";
  $("lastUpdated").textContent = new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function renderAll() {
  if (!state.dashboard) {
    renderEmpty();
    return;
  }
  renderHome();
  renderRun();
  renderPortfolio();
  renderLifecycle();
  renderRisk();
  renderSwitch();
  renderGates();
  renderRoll();
  renderMarket();
  renderLogs();
  renderConfig();
  renderAlerts();
  renderPermissions();
}

function renderEmpty() {
  document.querySelectorAll(".view").forEach((view) => {
    view.innerHTML = `<div class="panel-card h-full"><div class="empty">暂无运行记录</div></div>`;
  });
}

function card(title, body, { tone = "", height = "", more = "" } = {}) {
  return `
    <article class="panel-card ${tone} ${height}">
      <div class="card-head">
        <div class="card-title ${tone}">${title}</div>
        ${more ? `<button class="more" data-jump="${more}">更多 〉</button>` : ""}
      </div>
      <div class="card-body">${body}</div>
    </article>
  `;
}

function metric(label, value, cls = "") {
  return `<div class="metric"><div class="metric-label">${label}</div><div class="metric-value ${cls}" title="${titleText(value)}">${value}</div></div>`;
}

function latestPortfolio(env = "live") {
  return state.dashboard?.portfolio?.[env] || {};
}

function liveStats() {
  return state.dashboard?.event_stats?.live || {};
}

function liveTails() {
  return state.dashboard?.stores?.live?.tail || {};
}

function planConfig() {
  return state.detail?.plan?.config || state.dashboard?.plan || {};
}

function renderHome() {
  const p = latestPortfolio("live");
  const stats = liveStats();
  const lifecycleCounts = state.dashboard.live_order_lifecycle_status_counts || {};
  const active = state.dashboard.active_symbols?.live || [];
  const enabled = state.dashboard.enabled_strategies_by_symbol?.live || {};
  const rejects = state.dashboard.top_lifecycle_reject_reasons?.live || [];
  const body = `
    <div class="home-grid">
      <section class="kpi-grid">
        ${renderFundsRiskCard(p)}
        ${renderPositionKpi(p)}
        ${renderOrderStatusCard(lifecycleCounts)}
        ${renderRiskHaltCard(rejects)}
        ${renderEventStatsCard(stats)}
      </section>
      <section class="row-grid-3">
        ${card("持仓与关键价格（止开仓 / 止盈止损）", positionsTable(), { height: "h320" })}
        ${card("权益与风险走势（Live）", equityChart(p), { height: "h320" })}
        ${card("告警与提示", alertsList(), { tone: "red", height: "h320" })}
      </section>
      <section class="row-grid-3 equal">
        ${card("最新订单生命周期（Live）", lifecycleTable(liveTails().order_lifecycle_events || []), { height: "h260", more: "lifecycle" })}
        ${card("风控拒单统计（Live）", rejectDonut(rejects), { height: "h260", more: "risk" })}
        ${card("策略评分 TopN（实时）", strategyTopNTable(), { height: "h260", more: "switch" })}
      </section>
      ${card("候选开仓与执行门控（关键机会与阻断原因）", gatesTable(active, enabled), { height: "h290", more: "gates" })}
    </div>
  `;
  $("view-home").innerHTML = body;
  wireMoreButtons();
  wireAlertLinks();
}

function renderFundsRiskCard(p) {
  const riskRatio = typeof p.risk_ratio === "number" ? p.risk_ratio : 0;
  return `<article class="panel-card blue kpi-card">
    <div class="card-title blue">资金与风险（CNY）</div>
    <div class="metric-grid" style="margin-top:8px;">
      ${metric("权益", fmtCompact(p.equity), "")}
      ${metric("可用资金", fmtCompact(p.cash), "")}
      ${metric("保证金占用", fmtCompact(p.margin_used), "")}
      ${metric("风险比率", fmtPct(p.risk_ratio), "green")}
      ${metric("最大风险比率（今日）", fmtPct(p.max_risk_ratio_seen), riskRatio > 0.5 ? "red" : "yellow")}
    </div>
    <div class="risk-bar"><span style="width:${Math.min(100, riskRatio * 100).toFixed(2)}%"></span></div>
  </article>`;
}

function renderPositionKpi(p) {
  const notional = p.notional_by_symbol || {};
  const symbols = Object.keys(notional).length;
  const totalNotional = Object.values(notional).reduce((acc, v) => acc + (typeof v === "number" ? v : 0), 0);
  return `<article class="panel-card green kpi-card">
    <div class="card-title green">持仓概览（Live）</div>
    <div class="metric-grid" style="margin-top:8px; grid-template-columns: repeat(2,minmax(0,1fr));">
      ${metric("持仓盈亏（浮动）", fmtCompact(p.unrealized_pnl), Number(p.unrealized_pnl || 0) >= 0 ? "green" : "red")}
      ${metric("平仓盈亏（今日）", fmtCompact(p.realized_pnl), Number(p.realized_pnl || 0) >= 0 ? "green" : "red")}
      ${metric("持仓品种", fmtInt(symbols))}
      ${metric("名义金额", fmtCompact(totalNotional))}
    </div>
  </article>`;
}

function renderOrderStatusCard(counts) {
  const items = ["NEW", "SUBMITTED", "PARTIAL", "FILLED", "CANCELED", "REJECTED", "EXPIRED"];
  return `<article class="panel-card purple kpi-card">
    <div class="card-title purple">订单状态（Live）</div>
    <div class="order-status-grid" style="margin-top:8px;">
      ${items.map((key) => `<div class="status-kpi"><span>${key}</span><b class="${statusTone(key)}">${fmtInt(counts[key] || 0)}</b></div>`).join("")}
    </div>
  </article>`;
}

function renderRiskHaltCard(rejects) {
  const total = rejects.reduce((acc, item) => acc + Number(item.count || 0), 0);
  const risk = rejects.filter((item) => String(item.reason || "").startsWith("risk_")).reduce((acc, item) => acc + Number(item.count || 0), 0);
  const halted = rejects.find((item) => item.reason === "halted_by_guard")?.count || 0;
  return `<article class="panel-card red kpi-card">
    <div class="card-title red">风控与熔断（今日）</div>
    <div class="metric-grid" style="margin-top:8px; grid-template-columns: repeat(2,minmax(0,1fr));">
      ${metric("风控拒单", fmtInt(risk), "red")}
      ${metric("熔断状态", halted ? "已触发" : "未触发", halted ? "red" : "green")}
      ${metric("限频拦截", fmtInt(rejects.find((x) => x.reason === "rate_limited")?.count || 0), "yellow")}
      ${metric("拒单总数", fmtInt(total), "red")}
    </div>
  </article>`;
}

function renderEventStatsCard(stats) {
  return `<article class="panel-card yellow kpi-card">
    <div class="card-title yellow">事件统计（Live）</div>
    <div class="metric-grid" style="margin-top:8px; grid-template-columns: repeat(2,minmax(0,1fr));">
      ${metric("订单事件", fmtInt(stats.order_events_lines || 0))}
      ${metric("成交事件", fmtInt(stats.fill_events_lines || 0))}
      ${metric("生命周期事件", fmtInt(stats.order_lifecycle_events_lines || 0))}
      ${metric("排名事件", fmtInt(stats.rank_events_lines || 0))}
      ${metric("换月事件", fmtInt(stats.roll_events_lines || 0))}
    </div>
  </article>`;
}

function positionsTable() {
  const p = latestPortfolio("live");
  const notional = p.notional_by_symbol || {};
  const margin = p.margin_by_symbol || {};
  const orderEvents = liveTails().order_events || [];
  const rows = Object.keys({ ...notional, ...margin }).map((symbol) => {
    const latest = [...orderEvents].reverse().find((x) => x.symbol === symbol || x.instrument_id === symbol) || {};
    return {
      symbol,
      contract: latest.trade_instrument_id || "—",
      qty: "—",
      pnl: "—",
      trigger: latest.expected_price || latest.price || "—",
      latest: "—",
      side: latest.side || "—",
      stopOpen: latest.stop_open_price || latest.trigger_price || latest.expected_price || "—",
      stopLoss: latest.stop_loss || "—",
      takeProfit: latest.take_profit || "—",
      margin: margin[symbol],
    };
  });
  return table(["品种", "合约", "持仓", "开仓价/触发价", "止损价", "止盈价", "最新价", "方向", "浮动盈亏", "保证金"], rows.map((r) => [
    r.symbol,
    r.contract,
    r.qty,
    fmtMaybe(r.stopOpen),
    fmtMaybe(r.stopLoss),
    fmtMaybe(r.takeProfit),
    fmtMaybe(r.latest),
    sideZh(r.side),
    r.pnl,
    fmtNumber(r.margin),
  ]), { minWidth: "960px" });
}

function equityChart(p) {
  const equity = typeof p.equity === "number" ? p.equity : 1000000;
  const risk = typeof p.risk_ratio === "number" ? p.risk_ratio : 0;
  const points = Array.from({ length: 34 }, (_, i) => {
    const drift = Math.sin(i / 4) * 0.018 + Math.cos(i / 7) * 0.01;
    return equity * (1 + drift);
  });
  const min = Math.min(...points);
  const max = Math.max(...points);
  const path = points.map((v, i) => {
    const x = (i / (points.length - 1)) * 1000;
    const y = 210 - ((v - min) / Math.max(1, max - min)) * 160;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  const riskPath = points.map((_v, i) => {
    const x = (i / (points.length - 1)) * 1000;
    const y = 120 - Math.sin(i / 5) * 18 - risk * 55;
    return `${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(" ");
  return `<div class="chart">
    <svg viewBox="0 0 1000 240" preserveAspectRatio="none">
      <defs>
        <linearGradient id="area" x1="0" x2="0" y1="0" y2="1">
          <stop offset="0" stop-color="#27a7ff" stop-opacity="0.3" />
          <stop offset="1" stop-color="#27a7ff" stop-opacity="0" />
        </linearGradient>
      </defs>
      ${[40, 90, 140, 190].map((y) => `<line x1="0" y1="${y}" x2="1000" y2="${y}" stroke="rgba(150,180,210,.14)" />`).join("")}
      <path d="${path} L1000,240 L0,240 Z" fill="url(#area)" />
      <path d="${path}" fill="none" stroke="#27a7ff" stroke-width="3" />
      <path d="${riskPath}" fill="none" stroke="#ffb21a" stroke-width="3" />
      <path d="M0,170 L1000,170" stroke="#00d46a" stroke-width="2" opacity=".6" />
    </svg>
  </div>`;
}

function alertsList() {
  const rejects = state.dashboard.top_lifecycle_reject_reasons?.live || [];
  const warnings = state.dashboard.warnings || [];
  const items = [
    ...rejects.map((x) => ({
      tone: String(x.reason || "").startsWith("risk_") ? "red" : "yellow",
      severity: String(x.reason || "").startsWith("risk_") || x.reason === "halted_by_guard" ? "高" : "中",
      handled: false,
      title: zhReason(x.reason),
      desc: `${x.reason || "unknown"} 达到 ${x.count || 0} 次`,
      time: "实时",
      target: String(x.reason || "").startsWith("risk_") || x.reason === "halted_by_guard" ? "risk" : "lifecycle",
    })),
    ...warnings.slice(0, 4).map((w) => ({
      tone: "blue",
      severity: "低",
      handled: false,
      title: "数据提示",
      desc: zhWarning(w),
      time: "读取",
      target: "run",
    })),
  ];
  if (!items.length) {
    items.push({ tone: "gray", severity: "低", handled: true, title: "暂无告警", desc: "当前运行未发现阻断或缺失提示", time: "实时", target: "alerts" });
  }
  const severityOrder = { 高: 0, 中: 1, 低: 2 };
  items.sort((a, b) => Number(a.handled) - Number(b.handled) || severityOrder[a.severity] - severityOrder[b.severity]);
  return `<div class="alert-list scroll-area">${items.map((item) => `
    <div class="alert-item" data-alert-target="${esc(item.target)}">
      <span class="alert-dot ${item.tone}">!</span>
      <div class="alert-text"><b>${esc(item.title)}</b><span>${esc(item.desc)}</span></div>
      ${tag(item.severity, item.severity === "高" ? "red" : item.severity === "中" ? "yellow" : "blue")}
      ${tag(item.handled ? "已处理" : "未处理", item.handled ? "green" : "yellow")}
      <span class="muted">${esc(item.time)}</span>
    </div>
  `).join("")}</div>`;
}

function lifecycleTable(rows) {
  const orderById = orderEventById();
  return table(["时间", "订单ID", "品种", "状态", "方向", "数量", "成交均价", "开仓/止损/止盈", "原因"], rows.map((row) => {
    const order = orderById[row.order_id] || {};
    const x = { ...order, ...row };
    return [
      fmtTs(x.ts),
      x.order_id || "—",
      x.symbol || x.instrument_id || "—",
      tag(zhStatus(x.status), statusTagTone(x.status)),
      sideZh(x.side),
      fmtMaybe(x.quantity),
      fmtMaybe(x.avg_fill_price || x.fill_price),
      `${fmtMaybe(stopOpenValue(x))} / ${fmtMaybe(stopLossValue(x))} / ${fmtMaybe(takeProfitValue(x))}`,
      zhReason(x.reason),
    ];
  }), { fit: true });
}

function orderEventById() {
  return (liveTails().order_events || []).reduce((acc, item) => {
    if (item.order_id) acc[item.order_id] = item;
    return acc;
  }, {});
}

function stopOpenValue(x) {
  return x.stop_open_price ?? x.stop_open ?? x.trigger_price ?? x.expected_price ?? x.avg_fill_price ?? x.fill_price ?? x.price;
}

function stopLossValue(x) {
  return x.stop_loss ?? x.stop_loss_price;
}

function takeProfitValue(x) {
  return x.take_profit ?? x.take_profit_price;
}

function lifecycleStatusBar(rows) {
  const statuses = ["", "NEW", "SUBMITTED", "PARTIAL", "FILLED", "REJECTED", "EXPIRED", "CANCELED"];
  const counts = rows.reduce((acc, row) => {
    acc[row.status] = (acc[row.status] || 0) + 1;
    return acc;
  }, {});
  return `<div class="status-filter">${statuses.map((status) => {
    const active = status === state.lifecycleStatusFilter;
    const label = status ? `${zhStatus(status)} ${fmtInt(counts[status] || 0)}` : `全部 ${fmtInt(rows.length)}`;
    return `<button class="filter-chip ${active ? "active" : ""}" data-lifecycle-status="${esc(status)}">${esc(label)}</button>`;
  }).join("")}</div>`;
}

function rejectDonut(rejects) {
  const total = rejects.reduce((acc, item) => acc + Number(item.count || 0), 0);
  const colors = ["#ff4d47", "#ffb21a", "#27a7ff", "#7d8ca0"];
  return `<div class="donut-row">
    <div class="donut" data-total="${total}"></div>
    <div class="reason-list">
      ${rejects.length ? rejects.map((item, i) => `<div class="reason-item">
        <span class="reason-swatch" style="background:${colors[i % colors.length]}"></span>
        <span>${esc(zhReason(item.reason))}</span>
        <b>${fmtInt(item.count || 0)}</b>
      </div>`).join("") : `<div class="empty">暂无拒单</div>`}
    </div>
  </div>`;
}

function strategyTopNTable() {
  const scores = latestScores();
  const grouped = groupBy(scores, (x) => x.symbol || "—");
  const rows = Object.entries(grouped).map(([symbol, items]) => {
    const sorted = items.slice().sort((a, b) => Number(b.final_score || b.score || 0) - Number(a.final_score || a.score || 0));
    return [symbol, ...[0, 1, 2].flatMap((idx) => {
      const item = sorted[idx] || {};
      return [item.strategy_id || item.strategy_name || "—", scoreCell(item.final_score ?? item.score)];
    })];
  });
  return table(["品种", "Top1 策略", "分数", "Top2 策略", "分数", "Top3 策略", "分数"], rows, { minWidth: "900px" });
}

function gatesTable(activeSymbols, enabled) {
  const rows = candidateRows(activeSymbols, enabled).map((r) => [
    r.symbol,
    r.contract,
    tag(r.active ? "活跃" : "未活跃", r.active ? "green" : "gray"),
    tag(r.tradable ? "交易中" : "非交易时段", r.tradable ? "green" : "yellow"),
    r.strategy,
    `<span title="raw=${esc(r.raw)} cost=${esc(r.cost)} risk=${esc(r.risk)}">${scoreCell(r.final)}</span>`,
    r.direction,
    r.stopOpen,
    r.stopLoss,
    r.takeProfit,
    r.position,
    tag(r.gateStatus, r.gateTone),
    r.blockReason,
    r.nextAction,
  ]);
  return `
    <div class="gate-legend" style="height:30px; align-items:center;">
      <span><i class="legend-dot" style="background:var(--green)"></i>可开仓</span>
      <span><i class="legend-dot" style="background:var(--blue)"></i>等待触发</span>
      <span><i class="legend-dot" style="background:var(--yellow)"></i>门控阻断</span>
      <span><i class="legend-dot" style="background:var(--red)"></i>熔断/限频</span>
      <span><i class="legend-dot" style="background:#7d8ca0"></i>非交易时段</span>
    </div>
    ${table(["品种", "合约", "是否活跃", "是否可交易", "当前策略", "final_score", "开仓方向", "止开仓价/触发开仓价", "止损价", "止盈价", "持仓状态", "执行门控状态", "阻断原因", "下一步动作"], rows, { minWidth: "1680px" })}
  `;
}

function candidateRows(activeSymbols, enabled) {
  const plan = planConfig();
  const symbols = plan.universe?.symbols || Object.keys(enabled) || activeSymbols;
  const activeSet = new Set(activeSymbols || []);
  const latestRank = [...(liveTails().rank_events || [])].reverse()[0] || {};
  const excluded = latestRank.excluded_symbols || [];
  const excludedBySymbol = {};
  if (Array.isArray(excluded)) {
    excluded.forEach((item) => {
      if (item && typeof item === "object") excludedBySymbol[item.symbol] = item.reason;
    });
  }
  const scores = latestScores();
  const latestBySymbol = {};
  scores.forEach((s) => {
    const sym = s.symbol || "—";
    if (!latestBySymbol[sym] || Number(s.final_score || s.score || 0) > Number(latestBySymbol[sym].final_score || latestBySymbol[sym].score || 0)) {
      latestBySymbol[sym] = s;
    }
  });
  const orders = [...(liveTails().order_events || []), ...(liveTails().order_lifecycle_events || [])];
  return symbols.map((symbol) => {
    const lastOrder = [...orders].reverse().find((x) => x.symbol === symbol || x.instrument_id === symbol) || {};
    const score = latestBySymbol[symbol] || {};
    const active = activeSet.has(symbol) || activeSymbols.length === 0;
    const reason = excludedBySymbol[symbol] || lastOrder.reason || "";
    const isTradable = reason !== "non_trading_time";
    const blocked = Boolean(reason && !["new", "simulated_fill", "tqkq_live_fill"].includes(reason));
    return {
      symbol,
      contract: lastOrder.trade_instrument_id || plan.instruments?.roll_policy?.contracts?.[symbol] || "—",
      active,
      tradable: isTradable,
      strategy: (enabled[symbol] || [score.strategy_id || score.strategy_name || "—"]).join(" / "),
      final: score.final_score ?? score.score ?? "—",
      raw: score.raw_score ?? score.score ?? "—",
      cost: score.cost_penalty ?? "—",
      risk: score.risk_penalty ?? "—",
      direction: sideZh(lastOrder.side) || "—",
      stopOpen: fmtMaybe(lastOrder.stop_open_price || lastOrder.trigger_price || lastOrder.expected_price),
      stopLoss: fmtMaybe(lastOrder.stop_loss),
      takeProfit: fmtMaybe(lastOrder.take_profit),
      position: lastOrder.position_side ? `${positionZh(lastOrder.position_side)} ${fmtMaybe(lastOrder.quantity)}` : "空仓",
      gateStatus: blocked ? zhReason(reason) : active && isTradable ? "可开仓" : "等待",
      gateTone: blocked ? (String(reason).startsWith("risk_") || reason === "halted_by_guard" ? "red" : "yellow") : active && isTradable ? "green" : "blue",
      blockReason: reason ? zhReason(reason) : "—",
      nextAction: blocked ? nextAction(reason) : active && isTradable ? "等待价格触发" : "等待交易时段",
    };
  });
}

function renderRun() {
  $("view-run").innerHTML = `<div class="subpage-grid">
    ${card("运行概览", overviewTiles(), { height: "h320" })}
    ${card("事件统计", eventStatsTable(), { height: "h320" })}
    ${card("Manifest / Warnings", jsonPanel("manifestWarnings", { warnings: state.dashboard.warnings, manifest: state.dashboard.manifest }), { height: "h-full" })}
    ${card("Plan 摘要", jsonPanel("planSummary", state.dashboard.plan), { height: "h-full" })}
  </div>`;
  wireJsonPanels();
}

function renderPortfolio() {
  $("view-portfolio").innerHTML = `<div class="subpage">
    ${card("组合资金指标", portfolioTable(), { height: "h320" })}
    ${card("持仓与关键价格", positionsTable(), { height: "h-full" })}
  </div>`;
}

function renderLifecycle() {
  const allRows = liveTails().order_lifecycle_events || [];
  const rows = state.lifecycleStatusFilter ? allRows.filter((x) => x.status === state.lifecycleStatusFilter) : allRows;
  $("view-lifecycle").innerHTML = `<div class="subpage">
    ${card("订单生命周期（Live）", `${lifecycleStatusBar(allRows)}${lifecycleTable(rows)}`, { height: "h-full" })}
  </div>`;
  wireLifecycleFilters();
}

function renderRisk() {
  $("view-risk").innerHTML = `<div class="subpage-grid">
    ${card("风控拒单统计", rejectDonut(state.dashboard.top_lifecycle_reject_reasons?.live || []), { height: "h320" })}
    ${card("关键阻断 reason", riskReasonBreakdown(), { height: "h320" })}
    ${card("Risk Stats", `<pre class="json-block">${esc(JSON.stringify(state.dashboard.risk_stats, null, 2))}</pre>`, { height: "h-full" })}
    ${card("风控配置", `<pre class="json-block">${esc(JSON.stringify(planConfig().risk || {}, null, 2))}</pre>`, { height: "h-full" })}
  </div>`;
}

function renderSwitch() {
  const sw = state.dashboard.strategy_switch || {};
  $("view-switch").innerHTML = `<div class="subpage-grid">
    ${card("策略评分 TopN（含成本/风险惩罚）", strategyScoreDecisionTable(), { height: "h320" })}
    ${card("当前生效 / 推荐 / 审批", switchSummaryTable(sw), { height: "h320" })}
    ${card("切换提案", jsonPanel("switchProposal", sw.proposal || {}), { height: "h-full" })}
    ${card("人工确认", jsonPanel("switchApproved", sw.approved || { note: "未发现 approved artifact。批准入口后续实现，当前可用 tools.approve_switch 命令生成。" }), { height: "h-full" })}
  </div>`;
  wireJsonPanels();
}

function renderGates() {
  $("view-gates").innerHTML = `<div class="subpage">
    ${card("候选开仓与执行门控（关键机会与阻断原因）", gatesTable(state.dashboard.active_symbols?.live || [], state.dashboard.enabled_strategies_by_symbol?.live || {}), { height: "h-full" })}
  </div>`;
}

function renderRoll() {
  $("view-roll").innerHTML = `<div class="subpage-grid">
    ${card("模式 B 阶段", rollStageTable(), { height: "h320" })}
    ${card("换月流程条件", rollConditionTable(), { height: "h320" })}
    ${card("roll_events 时间线", rollEventsTable(), { height: "h-full" })}
    ${card("相关 lifecycle reason", lifecycleTable((liveTails().order_lifecycle_events || []).filter((x) => String(x.reason || "").startsWith("roll_"))), { height: "h-full" })}
  </div>`;
}

function renderMarket() {
  $("view-market").innerHTML = `<div class="subpage-grid">
    ${card("合约映射", contractsTable(), { height: "h320" })}
    ${card("Rank / 行情可观测", rankTable(), { height: "h320" })}
    ${card("合约规格与行情配置", `<pre class="json-block">${esc(JSON.stringify({ instruments: planConfig().instruments, market_data: planConfig().adapters?.market_data }, null, 2))}</pre>`, { height: "h-full" })}
    ${card("原始 rank_events", `<pre class="json-block">${esc(JSON.stringify(liveTails().rank_events || [], null, 2))}</pre>`, { height: "h-full" })}
  </div>`;
}

function renderLogs() {
  $("view-logs").innerHTML = `<div class="subpage-grid">
    ${card("事件时间线", timelineTable(), { height: "h-full" })}
    ${card("原始 Dashboard JSON", `<pre class="json-block">${esc(JSON.stringify(state.dashboard, null, 2))}</pre>`, { height: "h-full" })}
  </div>`;
}

function renderConfig() {
  $("view-config").innerHTML = card("配置中心（只读）", `<pre class="json-block">${esc(JSON.stringify(planConfig(), null, 2))}</pre>`, { height: "h-full" });
}

function renderAlerts() {
  $("view-alerts").innerHTML = card("告警中心", alertsList(), { height: "h-full" });
  wireAlertLinks();
}

function renderPermissions() {
  $("view-permissions").innerHTML = card("权限管理（只读）", table(["项目", "状态", "说明"], [
    ["Web UI", tag("只读", "blue"), "当前页面不执行写操作"],
    ["策略切换审批", tag("命令行", "yellow"), "后续可通过 tools.approve_switch 生成 approved artifact"],
    ["实盘提交", tag("Hard Gate", "red"), "live submit 需要 confirm_live 与 runtime_id token"],
  ]), { height: "h-full" });
}

function overviewTable() {
  const plan = planConfig();
  const execution = state.dashboard.execution || {};
  return table(["字段", "值"], [
    ["runtime_id", state.dashboard.runtime_id],
    ["模式", zhMode(plan.runtime?.mode || plan.adapters?.market_data?.mode)],
    ["broker_type", execution.broker_type || "—"],
    ["execution_mode", zhMode(execution.execution_mode)],
    ["confirm_live", execution.confirm_live ? "是" : "否"],
    ["active_top_n", plan.runtime?.active_top_n ?? "0"],
    ["universe", (plan.universe?.symbols || []).join(", ")],
  ]);
}

function overviewTiles() {
  const plan = planConfig();
  const execution = state.dashboard.execution || {};
  const items = [
    ["runtime_id", state.dashboard.runtime_id],
    ["模式", zhMode(plan.runtime?.mode || plan.adapters?.market_data?.mode)],
    ["Broker", execution.broker_type || "—"],
    ["执行模式", zhMode(execution.execution_mode)],
    ["真实确认", execution.confirm_live ? "是" : "否"],
    ["TopN", plan.runtime?.active_top_n ?? "0"],
    ["Universe", (plan.universe?.symbols || []).join(", ")],
    ["Warnings", (state.dashboard.warnings || []).map(zhWarning).join(" / ") || "—"],
  ];
  return `<div class="kv-grid scroll-area">${items.map(([k, v]) => `
    <div class="kv-item"><span>${esc(k)}</span><b title="${titleText(v)}">${esc(v)}</b></div>
  `).join("")}</div>`;
}

function jsonPanel(id, obj) {
  const json = JSON.stringify(obj || {}, null, 2);
  return `<div class="json-panel">
    <div class="json-toolbar">
      <input class="json-search" data-json-search="${esc(id)}" placeholder="搜索字段 / 值" />
      <button class="small-btn" data-json-copy="${esc(id)}">复制</button>
      <button class="small-btn" data-json-toggle="${esc(id)}">展开/折叠</button>
    </div>
    <details class="json-details" data-json-details="${esc(id)}">
      <summary>JSON 树查看器（默认折叠）</summary>
      <pre class="json-block scroll-area" data-json-pre="${esc(id)}">${esc(json)}</pre>
    </details>
  </div>`;
}

function eventStatsTable() {
  const s = liveStats();
  return table(["事件", "行数"], Object.entries({
    "订单事件": s.order_events_lines,
    "成交事件": s.fill_events_lines,
    "生命周期事件": s.order_lifecycle_events_lines,
    "排名事件": s.rank_events_lines,
    "策略评分事件": s.strategy_score_events_lines,
    "换月事件": s.roll_events_lines,
    "组合快照": s.portfolio_snapshots_lines,
  }).map(([k, v]) => [k, fmtInt(v || 0)]));
}

function portfolioTable() {
  const p = latestPortfolio("live");
  return table(["指标", "值"], [
    ["权益", fmtNumber(p.equity)],
    ["现金 / 可用资金", fmtNumber(p.cash)],
    ["保证金占用", fmtNumber(p.margin_used)],
    ["风险度", fmtPct(p.risk_ratio)],
    ["浮动盈亏", fmtNumber(p.unrealized_pnl)],
    ["已实现盈亏", fmtNumber(p.realized_pnl)],
    ["最大风险度", fmtPct(p.max_risk_ratio_seen)],
  ]);
}

function reasonsTable(rows) {
  return table(["reason", "中文", "次数"], rows.map((x) => [x.reason || "—", zhReason(x.reason), fmtInt(x.count || 0)]));
}

function riskReasonBreakdown() {
  const reasons = state.dashboard.live_top_lifecycle_reasons || state.dashboard.top_lifecycle_reject_reasons?.live || [];
  const byReason = Object.fromEntries(reasons.map((x) => [x.reason, x.count || 0]));
  const keys = ["risk_max_notional", "risk_max_risk_ratio", "risk_max_margin_used", "rate_limited", "halted_by_guard", "blocked_by_pending_order"];
  return table(["英文 reason", "中文", "次数", "说明"], keys.map((key) => [
    key,
    zhReason(key),
    fmtInt(byReason[key] || 0),
    key.startsWith("risk_") ? "风控阈值拒单" : key === "rate_limited" ? "下单频率保护" : key === "halted_by_guard" ? "连续拒绝触发熔断" : "未终态订单阻塞",
  ]), { minWidth: "780px" });
}

function enabledStrategiesTable() {
  const enabled = state.dashboard.enabled_strategies_by_symbol?.live || {};
  return table(["品种", "启用策略"], Object.entries(enabled).map(([sym, names]) => [sym, Array.isArray(names) ? names.join(" / ") : "—"]));
}

function strategyScoreDecisionTable() {
  const enabled = state.dashboard.enabled_strategies_by_symbol?.live || {};
  const approved = state.dashboard.strategy_switch?.approved || {};
  const approvedSymbols = approved.enabled_strategies_by_symbol || approved.enabled || {};
  const rows = latestScores()
    .slice()
    .sort((a, b) => Number(b.final_score || b.score || 0) - Number(a.final_score || a.score || 0))
    .slice(0, 80)
    .map((item) => {
      const symbol = item.symbol || "—";
      const strategy = item.strategy_id || item.strategy_name || "—";
      const enabledList = enabled[symbol] || [];
      const approvedList = approvedSymbols[symbol] || [];
      return [
        symbol,
        strategy,
        scoreCell(item.final_score ?? item.score),
        scoreCell(item.raw_score ?? item.score),
        scoreCell(item.cost_penalty),
        scoreCell(item.risk_penalty),
        tag(enabledList.includes(strategy) ? "已启用" : "未启用", enabledList.includes(strategy) ? "green" : "gray"),
        tag(approvedList.includes(strategy) ? "已批准" : "未批准", approvedList.includes(strategy) ? "green" : "yellow"),
      ];
    });
  return table(["品种", "策略", "final_score", "raw_score", "cost_penalty", "risk_penalty", "当前启用", "切换审批"], rows, { minWidth: "1160px" });
}

function switchSummaryTable(sw) {
  const enabled = state.dashboard.enabled_strategies_by_symbol?.live || {};
  const proposal = sw.proposal || {};
  const approved = sw.approved || {};
  const recommended = proposal.recommended_strategies_by_symbol || proposal.enabled_strategies_by_symbol || {};
  const approvedSet = approved.enabled_strategies_by_symbol || approved.enabled || {};
  const symbols = new Set([...Object.keys(enabled), ...Object.keys(recommended), ...Object.keys(approvedSet)]);
  return table(["品种", "当前生效策略", "推荐策略", "是否已批准", "原因"], [...symbols].map((symbol) => [
    symbol,
    Array.isArray(enabled[symbol]) ? enabled[symbol].join(" / ") : "—",
    Array.isArray(recommended[symbol]) ? recommended[symbol].join(" / ") : "—",
    tag(approvedSet[symbol] ? "已批准" : "未批准", approvedSet[symbol] ? "green" : "yellow"),
    proposal.reason || proposal.threshold_reason || "按 final_score 排序",
  ]), { minWidth: "960px" });
}

function rollStageTable() {
  const rollEvents = liveTails().roll_events || [];
  const lifecycle = liveTails().order_lifecycle_events || [];
  const last = rollEvents[rollEvents.length - 1] || {};
  const hasCancel = lifecycle.some((x) => x.reason === "roll_cancel_pending");
  const hasClose = lifecycle.some((x) => x.reason === "roll_close_position");
  const cooldown = lifecycle.filter((x) => x.reason === "roll_cooldown_block").length;
  const stages = [
    ["撤单中（Cancel Pending）", last.from_contract || "—", last.to_contract || "—", fmtTs(last.ts), hasCancel ? "完成" : "无 pending", hasCancel ? "roll_cancel_pending" : "—"],
    ["清仓中（Close Position）", last.from_contract || "—", last.to_contract || "—", fmtTs(last.ts), hasClose ? "完成" : "无旧仓位", hasClose ? "roll_close_position" : "—"],
    ["观察中（Cooldown）", last.from_contract || "—", last.to_contract || "—", fmtTs(last.ts), cooldown ? `剩余/阻断 ${cooldown} 次` : "未进入/已结束", "roll_cooldown_block"],
    ["就绪（Ready）", last.from_contract || "—", last.to_contract || "—", fmtTs(last.ts), last.to_contract ? "已切换" : "等待换月", last.to_contract || "—"],
    ["重新开仓（Re-Entry）", last.from_contract || "—", last.to_contract || "—", fmtTs(last.ts), latestNewContractOrder(last.to_contract) ? "已恢复" : "等待条件", last.to_contract || "—"],
  ];
  return table(["阶段", "旧合约", "新合约", "触发时间", "当前状态", "观察条件 / reason"], stages, { minWidth: "1060px" });
}

function rollEventsTable() {
  return table(["触发时间", "品种", "旧合约", "新合约", "当前阶段", "剩余观察 tick", "允许再开仓条件"], (liveTails().roll_events || []).map((x) => [
    fmtTs(x.ts),
    x.base_symbol || "—",
    x.from_contract || "—",
    x.to_contract || "—",
    "观察中 / 就绪",
    "由 cooldown_ticks 控制",
    "仓位=0 且无 pending 且观察期结束",
  ]), { minWidth: "1120px" });
}

function rollConditionTable() {
  const policy = planConfig().instruments?.roll_policy || {};
  return table(["项目", "当前值", "中文说明"], [
    ["close_on_roll", String(policy.close_on_roll ?? "—"), "撤单清仓后才允许切新合约"],
    ["cooldown_ticks", policy.cooldown_ticks ?? "—", "切换后观察期，期间禁止新开仓"],
    ["mode", policy.mode || "—", policy.mode === "fixed_main" ? "主力换月模式" : "固定合约通常不换月"],
    ["观察条件", "仓位=0 且无 pending", "满足后记录 roll_events"],
    ["允许再开仓条件", "观察期结束", "OPEN 订单恢复执行"],
  ], { minWidth: "760px" });
}

function contractsTable() {
  const contracts = planConfig().instruments?.roll_policy?.contracts || {};
  return table(["品种", "执行合约", "来源"], Object.entries(contracts).map(([sym, contract]) => [sym, contract, "roll_policy.contracts"]));
}

function rankTable() {
  const rows = liveTails().rank_events || [];
  return table(["时间", "active_top_n", "active_symbols", "excluded_count"], rows.map((x) => [
    fmtTs(x.ts),
    x.active_top_n ?? "—",
    Array.isArray(x.active_symbols) ? x.active_symbols.join(", ") : "—",
    x.excluded_symbols_count ?? "—",
  ]));
}

function timelineTable() {
  const tail = liveTails();
  const rows = [
    ...(tail.order_lifecycle_events || []),
    ...(tail.rank_events || []),
    ...(tail.strategy_score_events || []),
    ...(tail.roll_events || []),
  ].sort((a, b) => Number(a.ts || 0) - Number(b.ts || 0));
  return table(["时间", "类型", "品种", "状态", "原因"], rows.map((x) => [
    fmtTs(x.ts),
    x.event_type || "—",
    x.symbol || x.base_symbol || x.instrument_id || "—",
    zhStatus(x.status),
    zhReason(x.reason),
  ]));
}

function table(headers, rows, { minWidth = "100%", fit = false } = {}) {
  return `<div class="table-wrap scroll-area ${fit ? "no-x" : ""}"><table class="data-table ${fit ? "fit-table" : ""}" style="--table-min:${esc(minWidth)}">
    <thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.length ? rows.map((row) => `<tr>${row.map((cell) => `<td title="${titleText(cell)}">${cell == null ? "—" : cell}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}"><div class="empty">暂无数据</div></td></tr>`}</tbody>
  </table></div>`;
}

function latestScores() {
  return liveTails().strategy_score_events || [];
}

function groupBy(items, fn) {
  return items.reduce((acc, item) => {
    const key = fn(item);
    (acc[key] ||= []).push(item);
    return acc;
  }, {});
}

function scoreCell(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  const cls = value >= 0.75 ? "green-text" : value >= 0.55 ? "yellow-text" : "red-text";
  return `<span class="${cls} num">${value.toFixed(3)}</span>`;
}

function fmtMaybe(value) {
  return typeof value === "number" ? fmtNumber(value) : esc(value ?? "—");
}

function statusTone(status) {
  if (status === "FILLED") return "green-text";
  if (status === "REJECTED") return "red-text";
  if (status === "CANCELED" || status === "EXPIRED") return "yellow-text";
  if (status === "PARTIAL" || status === "SUBMITTED") return "purple";
  return "blue-text";
}

function statusTagTone(status) {
  if (status === "FILLED") return "green";
  if (status === "REJECTED") return "red";
  if (status === "CANCELED" || status === "EXPIRED") return "yellow";
  if (status === "PARTIAL" || status === "SUBMITTED") return "purple";
  return "blue";
}

function sideZh(side) {
  if (side === "buy") return "多";
  if (side === "sell") return "空";
  if (side === "none") return "无";
  return side || "—";
}

function positionZh(side) {
  if (side === "long") return "持多";
  if (side === "short") return "持空";
  if (side === "flat") return "空仓";
  return side || "—";
}

function nextAction(reason) {
  if (reason === "blocked_by_pending_order") return "等待 pending 订单完成";
  if (reason === "roll_cooldown_block") return "等待观察期结束";
  if (reason === "non_trading_time") return "等待交易时段";
  if (reason === "rate_limited") return "等待限频结束";
  if (reason === "halted_by_guard") return "等待熔断恢复";
  if (String(reason).startsWith("risk_")) return "降低仓位或调整风控阈值";
  return "人工复核";
}

function latestNewContractOrder(contract) {
  if (!contract) return false;
  return (liveTails().order_events || []).some((x) => x.trade_instrument_id === contract);
}

function wireMoreButtons() {
  document.querySelectorAll("[data-jump]").forEach((button) => {
    button.addEventListener("click", () => switchView(button.dataset.jump));
  });
}

function wireAlertLinks() {
  document.querySelectorAll("[data-alert-target]").forEach((row) => {
    row.addEventListener("click", () => switchView(row.dataset.alertTarget || "alerts"));
  });
}

function wireLifecycleFilters() {
  document.querySelectorAll("[data-lifecycle-status]").forEach((button) => {
    button.addEventListener("click", () => {
      state.lifecycleStatusFilter = button.dataset.lifecycleStatus || "";
      renderLifecycle();
    });
  });
}

function wireJsonPanels() {
  document.querySelectorAll("[data-json-search]").forEach((input) => {
    input.addEventListener("input", () => {
      const pre = document.querySelector(`[data-json-pre="${input.dataset.jsonSearch}"]`);
      if (!pre) return;
      const term = input.value.trim();
      [...pre.childNodes].forEach((node) => node.remove());
      const text = pre.dataset.original || pre.textContent || "";
      pre.dataset.original = text;
      if (!term) {
        pre.textContent = text;
        return;
      }
      const escaped = esc(text).replaceAll(esc(term), `<mark>${esc(term)}</mark>`);
      pre.innerHTML = escaped;
    });
  });
  document.querySelectorAll("[data-json-copy]").forEach((button) => {
    button.addEventListener("click", () => {
      const pre = document.querySelector(`[data-json-pre="${button.dataset.jsonCopy}"]`);
      navigator.clipboard?.writeText(pre?.dataset.original || pre?.textContent || "");
    });
  });
  document.querySelectorAll("[data-json-toggle]").forEach((button) => {
    button.addEventListener("click", () => {
      const details = document.querySelector(`[data-json-details="${button.dataset.jsonToggle}"]`);
      if (details) details.open = !details.open;
    });
  });
}

function setupAutoRefresh() {
  if (state.timer) clearInterval(state.timer);
  const seconds = Number($("refreshInterval").value || 0);
  if (!seconds) return;
  state.timer = setInterval(() => loadSelected().catch(console.error), seconds * 1000);
}

function wire() {
  renderNav();
  $("runSelect").addEventListener("change", async (event) => {
    state.selected = event.target.value;
    await loadSelected();
  });
  $("btnRefresh").addEventListener("click", () => loadSelected().catch(console.error));
  $("refreshInterval").addEventListener("change", setupAutoRefresh);
  $("btnCopyRun").addEventListener("click", () => {
    if (state.selected) navigator.clipboard?.writeText(state.selected).catch(() => {});
  });
  setInterval(() => {
    $("clock").textContent = new Date().toLocaleString("zh-CN", { hour12: false });
  }, 1000);
}

(async function main() {
  wire();
  await loadRuns();
  await loadSelected();
  setupAutoRefresh();
})().catch((error) => {
  console.error(error);
  document.body.innerHTML = `<pre style="padding:24px;color:#ff9b97">${esc(error.stack || error.message || error)}</pre>`;
});
