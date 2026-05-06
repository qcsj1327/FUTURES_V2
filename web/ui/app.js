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
  local: "本地模拟",
  simulated: "模拟提交",
  dryrun: "实盘演练",
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
  broker_fill: "柜台成交",
  broker_partial_fill: "柜台部分成交",
  blocked_by_pending_order: "待处理订单阻塞",
  duplicate_same_tick: "同 tick 重复下单",
  expired: "订单过期",
  canceled: "已撤单",
  risk_position_limit: "超过持仓数量上限",
  risk_max_notional: "超过持仓规模上限",
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
  quote_not_recorded: "未记录行情价",
  contract_quote_unmapped: "合约未映射行情",
  insufficient_events: "样本不足",
  non_trading_time: "非交易时段",
  pending_order: "待处理订单",
  unknown: "未知原因",
  approved_artifact_present: "已晋升",
  auto_promotion_approved: "已自动晋升",
  auto_promotion_waiting_for_scores: "等待策略评分",
  rejected_artifact_present: "已拒绝",
  proposal_requires_approval: "等待自动晋升",
  proposal_missing_or_waiting_for_scores: "等待策略评分提案",
  approval_flow_disabled: "未启用策略切换",
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
  missing_current_summary: "缺少当前摘要",
  missing_decision: "缺少决策结果",
  missing_approved: "缺少审批结果",
  missing_strategy_switch_approved: "缺少策略切换晋升结果",
};

const PROJECTION_SOURCE_ZH = {
  portfolio_snapshot: "组合快照",
  broker_sync_observation: "账户同步诊断",
  strategy_switch_proposal: "策略切换提案",
  rank_events: "活跃品种排名",
  rank_events_scores: "排名评分",
  universe: "品种池",
  none: "暂无来源",
};

const PRICE_SOURCE_ZH = {
  market_price: "行情事件",
  fill_price: "成交价",
  avg_fill_price: "成交均价",
  none: "未记录",
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

function isLogicTick(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value < 1000000000;
}

function fmtEventTime(value) {
  if (isLogicTick(value)) return `tick ${fmtInt(value)}`;
  return fmtTs(value);
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

function zhProjectionSource(code) {
  return PROJECTION_SOURCE_ZH[code] || "系统整理";
}

function zhPriceSource(code) {
  return PRICE_SOURCE_ZH[code] || code || "—";
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

async function apiPost(path, body = {}) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(`${response.status} ${response.statusText}: ${text}`);
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

function metric(label, value, cls = "", title = value) {
  return `<div class="metric"><div class="metric-label" title="${esc(label)}">${label}</div><div class="metric-value ${cls}" title="${titleText(title)}">${value}</div></div>`;
}

function currentScope() {
  const exec = projection()?.execution_state || {};
  const scope = exec.datastore_scope || exec.runtime_profile || planConfig().runtime?.mode;
  return ["local", "dryrun", "live"].includes(scope) ? scope : "unknown";
}

function scopeTitle() {
  return currentScope().toUpperCase();
}

function scopedTitle(title) {
  return `${title}（${scopeTitle()}）`;
}

function latestPortfolio(scope = currentScope()) {
  return projection()?.portfolio?.[scope] || state.dashboard?.portfolio?.[scope] || {};
}

function currentStats() {
  return state.dashboard?.event_stats?.[currentScope()] || {};
}

function currentTails() {
  return state.dashboard?.stores?.[currentScope()]?.tail || {};
}

function projection() {
  return state.dashboard?.dashboard_projection || {};
}

function projectionScope(key, scope = currentScope()) {
  return projection()?.[key]?.[scope] || {};
}

function projectionItems(key) {
  const block = projectionScope(key);
  return Array.isArray(block.items) ? block.items : [];
}

function projectionStrategySwitch() {
  return projection()?.strategy_switch || state.dashboard?.strategy_switch || {};
}

function projectionEnabledStrategies() {
  return projectionStrategySwitch().enabled_strategies_by_symbol || {};
}

function projectionStrategyScores() {
  return projectionScope("strategy_scores");
}

function quoteFor(symbol, contract) {
  const quotes = projectionScope("quotes");
  return quotes.by_symbol?.[symbol] || quotes.by_contract?.[contract] || null;
}

function quoteUnavailableLabel(q) {
  return zhReason(q?.reason || "quote_not_recorded");
}

function totalPositionQty() {
  return projectionItems("positions").reduce((acc, item) => {
    const qty = typeof item.quantity === "number" ? item.quantity : 0;
    return acc + Math.abs(qty);
  }, 0);
}

function planConfig() {
  return state.detail?.plan?.effective_config_summary || state.dashboard?.plan?.effective_config_summary || state.dashboard?.plan || {};
}

function topNEnabled() {
  return Number(planConfig().runtime?.active_top_n || 0) > 0;
}

function activeSymbolsForDisplay() {
  return projectionScope("active_symbols").symbols || [];
}

function activeSymbolsLabel() {
  const active = projectionScope("active_symbols");
  const symbols = active.symbols || [];
  return symbols.length
    ? `${symbols.join(", ")}（来源：${zhProjectionSource(active.source)}）`
    : "暂无活跃品种";
}

function renderHome() {
  const p = latestPortfolio();
  const stats = currentStats();
  const orderStatusCounts = projectionScope("order_status").counts || {};
  const active = activeSymbolsForDisplay();
  const enabled = projectionEnabledStrategies();
  const rejects = projection()?.risk_summary?.[currentScope()]?.top_risk_reject_reasons || state.dashboard.top_lifecycle_reject_reasons?.[currentScope()] || [];
  const body = `
    <div class="home-grid">
      <section class="kpi-grid">
        ${renderFundsRiskCard(p)}
        ${renderPositionKpi(p)}
        ${renderOrderStatusCard(orderStatusCounts)}
        ${renderRiskHaltCard(rejects)}
        ${renderEventStatsCard(stats)}
      </section>
      <section class="row-grid-3">
    ${card("持仓与关键价格（开仓均价 / 止盈止损）", positionsTable({ summary: true }), { height: "h360" })}
        ${card(scopedTitle("待成交 / 挂单"), pendingOrdersTable({ summary: true }), { height: "h360", more: "portfolio" })}
        ${card(scopedTitle("权益与风险走势"), equityChart(p), { height: "h320" })}
      </section>
      <section class="row-grid-3 equal">
        ${card(scopedTitle("最新订单生命周期事件"), homeLifecycleTable(projectionScope("lifecycle_view").items || currentTails().order_lifecycle_events || []), { height: "h260", more: "lifecycle" })}
        ${card(scopedTitle("风控拒单统计"), rejectDonut(rejects), { height: "h260", more: "risk" })}
        ${card("告警中心", alertsList(), { tone: "red", height: "h260", more: "alerts" })}
      </section>
      ${card("候选开仓与执行门控（关键机会与阻断原因）", gatesTable(active, enabled, { summary: true }), { height: "h360", more: "gates" })}
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
      ${metric("权益", fmtCompact(p.equity), "", fmtNumber(p.equity))}
      ${metric("可用资金", fmtCompact(p.cash), "", fmtNumber(p.cash))}
      ${metric("保证金占用", fmtCompact(p.margin_used), "", fmtNumber(p.margin_used))}
      ${metric("风险比率", fmtPct(p.risk_ratio), "green")}
      ${metric("最大风险比率（今日）", fmtPct(p.max_risk_ratio_seen), riskRatio > 0.5 ? "red" : "yellow")}
    </div>
    <div class="risk-bar"><span style="width:${Math.min(100, riskRatio * 100).toFixed(2)}%"></span></div>
  </article>`;
}

function renderPositionKpi(p) {
  const positions = projectionItems("positions");
  const symbols = new Set(positions.map((pos) => pos.symbol).filter(Boolean)).size;
  const totalQty = totalPositionQty();
  return `<article class="panel-card green kpi-card">
    <div class="card-title green">${scopedTitle("持仓概览")}</div>
    <div class="metric-grid" style="margin-top:8px;">
      ${metric("持仓盈亏（浮动）", fmtCompact(p.unrealized_pnl), Number(p.unrealized_pnl || 0) >= 0 ? "green" : "red", fmtNumber(p.unrealized_pnl))}
      ${metric("平仓盈亏（已实现）", fmtCompact(p.realized_pnl), Number(p.realized_pnl || 0) >= 0 ? "green" : "red", fmtNumber(p.realized_pnl))}
      ${metric("持仓品种", fmtInt(symbols))}
      ${metric("总持仓手数", fmtMaybe(totalQty))}
      ${metric("当前权益", fmtCompact(p.equity), "", fmtNumber(p.equity))}
      ${metric("可用资金", fmtCompact(p.cash), "", fmtNumber(p.cash))}
    </div>
  </article>`;
}

function renderOrderStatusCard(counts) {
  const items = ["NEW", "SUBMITTED", "PARTIAL", "FILLED", "CANCELED", "REJECTED", "EXPIRED"];
  return `<article class="panel-card purple kpi-card">
    <div class="card-title purple">${scopedTitle("订单状态")}</div>
    <div class="order-status-grid" style="margin-top:8px;">
      ${items.map((key) => `<div class="status-kpi"><span title="${esc(key)}">${zhStatus(key)}</span><b class="${statusTone(key)}">${fmtInt(counts[key] || 0)}</b></div>`).join("")}
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
    <div class="card-title yellow">${scopedTitle("事件统计")}</div>
    <div class="metric-grid" style="margin-top:8px; grid-template-columns: repeat(3,minmax(0,1fr));">
      ${metric("订单事件", fmtInt(stats.order_events_lines || 0))}
      ${metric("成交事件", fmtInt(stats.fill_events_lines || 0))}
      ${metric("生命周期事件", fmtInt(stats.order_lifecycle_events_lines || 0))}
      ${metric("评分事件", fmtInt(stats.strategy_score_events_lines || 0))}
      ${metric("排名事件", fmtInt(stats.rank_events_lines || 0))}
      ${metric("换月事件", fmtInt(stats.roll_events_lines || 0))}
    </div>
  </article>`;
}

function positionsTable({ summary = false } = {}) {
  const p = latestPortfolio();
  const margin = p.margin_by_symbol || {};
  const rows = projectionItems("positions").map((pos) => {
    const symbol = pos.symbol || "—";
    const contract = pos.trade_instrument_id || null;
    const quote = quoteFor(symbol, contract);
    const latestPrice = quote?.latest_market_price;
    return {
      symbol,
      contract: contract || "—",
      position: `${positionZh(pos.position_side)} ${fmtMaybe(pos.quantity)}`,
      pnl: fmtNumber(pos.unrealized_pnl ?? symbolValue(p.unrealized_pnl_by_symbol, symbol)),
      entry: pos.avg_price ?? null,
      latest: latestPrice,
      latestReason: quote?.available ? "ok" : quoteUnavailableLabel(quote),
      stopLoss: quote?.stop_loss ?? null,
      takeProfit: quote?.take_profit ?? null,
      margin: margin[symbol],
      source: pos.source || "—",
    };
  });
  const mapped = rows.map((r) => [
    r.symbol,
    r.contract,
    r.position,
    fmtMaybe(r.entry),
    r.latest == null ? `<span class="muted">${esc(r.latestReason)}</span>` : fmtMaybe(r.latest),
    r.pnl,
    fmtPriceOrUnset(r.stopLoss),
    fmtPriceOrUnset(r.takeProfit),
    fmtNumber(r.margin),
    r.source,
  ]);
  if (summary) {
    return table(
      ["品种", "合约", "持仓方向/手数", "开仓均价", "最新价", "浮动盈亏", "止损价", "止盈价", "保证金", "来源"],
      mapped,
      { minWidth: "1280px", className: "summary-table", emptyMessage: "暂无真实持仓。" },
    );
  }
  return table(["品种", "合约", "持仓方向/手数", "开仓均价", "最新价", "浮动盈亏", "止损价", "止盈价", "保证金", "来源"], mapped, {
    minWidth: "1280px",
    emptyMessage: "暂无真实持仓。",
  });
}

function pendingOrdersTable({ summary = false } = {}) {
  const rows = projectionItems("pending_orders").map((item) => [
    item.order_id || "—",
    item.symbol || "—",
    item.trade_instrument_id || "—",
    sideZh(item.side),
    positionZh(item.position_side),
    fmtMaybe(item.quantity),
    fmtMaybe(item.filled_quantity),
    fmtMaybe(item.remaining_quantity),
    fmtNumber(item.unrealized_pnl),
    fmtPriceOrUnset(item.order_price),
    fmtPriceOrUnset(item.stop_loss),
    fmtPriceOrUnset(item.take_profit),
    tag(zhStatus(item.status), statusTagTone(item.status)),
    zhReason(item.reason),
    fmtEventTime(item.ts),
  ]);
  if (summary) {
    return table(
      ["订单ID", "品种", "合约", "方向", "持仓方向", "数量", "已成交", "剩余", "订单浮盈", "委托价", "止损价", "止盈价", "状态", "原因", "时间"],
      rows,
      { minWidth: "1620px", className: "summary-table", emptyMessage: "暂无待成交 / 挂单。" },
    );
  }
  return table(["订单ID", "品种", "合约", "方向", "持仓方向", "数量", "已成交", "剩余", "订单浮盈", "委托价", "止损价", "止盈价", "状态", "原因", "时间"], rows, {
    minWidth: "1620px",
    emptyMessage: "暂无待成交 / 挂单。",
  });
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
  return `<div class="chart-legend">
    <span><i style="background:var(--blue)"></i>权益</span>
    <span><i style="background:var(--yellow)"></i>风险比率</span>
    <span><i style="background:var(--green)"></i>保证金占用</span>
  </div><div class="chart">
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
  const alerts = projection()?.alerts?.items || [];
  const severityByLevel = { error: "高", warning: "中", info: "低" };
  const items = alerts.map((x) => ({
    tone: x.level === "error" ? "red" : x.level === "warning" ? "yellow" : "blue",
    severity: severityByLevel[x.level] || "低",
    handled: false,
    title: zhReason(x.code),
    desc: x.message && x.message !== x.code ? x.message : zhReason(x.code),
    time: x.source ? "运行数据" : "系统检测",
    target: String(x.source || "").includes("risk") || String(x.code || "").startsWith("risk_") ? "risk" : "lifecycle",
  }));
  if (!items.length) {
    items.push({ tone: "gray", severity: "低", handled: true, title: "暂无告警", desc: "当前运行未发现主要告警", time: "实时", target: "alerts" });
  }
  const severityOrder = { 高: 0, 中: 1, 低: 2 };
  items.sort((a, b) => Number(a.handled) - Number(b.handled) || severityOrder[a.severity] - severityOrder[b.severity]);
  return `<div class="alert-list scroll-area">${items.slice(0, 5).map((item) => `
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
  return table(["时间/tick", "事件/订单ID", "品种", "状态", "方向", "数量", "成交均价", "订单浮盈", "开仓价", "止损价", "止盈价", "原因"], rows.map((row) => {
    const order = orderById[row.order_id] || {};
    const x = { ...order, ...row };
    return [
      fmtEventTime(x.event_time ?? x.created_at ?? x.observed_at ?? x.ts),
      x.order_id || "—",
      x.symbol || x.instrument_id || "—",
      tag(zhStatus(x.status), statusTagTone(x.status)),
      sideZh(x.side),
      fmtMaybe(x.quantity),
      fmtMaybe(x.avg_fill_price || x.fill_price),
      fmtNumber(orderUnrealizedPnl(x)),
      fmtPriceState(stopOpenValue(x), x.reason),
      fmtPriceState(stopLossValue(x), x.reason),
      fmtPriceState(takeProfitValue(x), x.reason),
      zhReason(x.reason),
    ];
  }), { minWidth: "1280px" });
}

function homeLifecycleTable(rows) {
  const orderById = orderEventById();
  const compact = rows.slice(-12).reverse().map((row) => {
    const order = orderById[row.order_id] || {};
    const x = { ...order, ...row };
    return [
      fmtEventTime(x.event_time ?? x.created_at ?? x.observed_at ?? x.ts),
      tag(zhStatus(x.status), statusTagTone(x.status)),
      x.symbol || x.instrument_id || "—",
      `${fmtPriceState(stopOpenValue(x), x.reason)} / ${fmtPriceState(stopLossValue(x), x.reason)} / ${fmtPriceState(takeProfitValue(x), x.reason)}`,
      zhReason(x.reason),
    ];
  });
  return `${compactStatusBar(rows)}${table(["时间", "状态", "品种", "开仓/止损/止盈", "原因"], compact, {
    fit: true,
    className: "summary-table",
        colWidths: ["86px", "82px", "72px", "150px", "160px"],
  })}`;
}

function orderEventById() {
  return (currentTails().order_events || []).reduce((acc, item) => {
    if (item.order_id) acc[item.order_id] = item;
    return acc;
  }, {});
}

function orderUnrealizedPnl(x) {
  if (typeof x.unrealized_pnl === "number" && Number.isFinite(x.unrealized_pnl)) {
    return x.unrealized_pnl;
  }
  const filled = typeof x.filled_quantity === "number" ? x.filled_quantity : 0;
  const avg = typeof x.avg_fill_price === "number"
    ? x.avg_fill_price
    : typeof x.fill_price === "number"
      ? x.fill_price
      : null;
  const quote = quoteFor(x.symbol || x.instrument_id, x.trade_instrument_id);
  const latest = typeof quote?.latest_market_price === "number"
    ? quote.latest_market_price
    : typeof x.latest_market_price === "number"
      ? x.latest_market_price
      : typeof x.market_price === "number"
        ? x.market_price
        : null;
  if (!filled || avg == null || latest == null) return null;
  const isShort = x.position_side === "short" || x.side === "sell";
  return (isShort ? avg - latest : latest - avg) * filled;
}

function stopOpenValue(x) {
  return x.stop_open_price ?? x.stop_open ?? x.trigger_price ?? x.order_price ?? x.price ?? x.expected_price;
}

function stopLossValue(x) {
  return x.stop_loss ?? x.stop_loss_price;
}

function takeProfitValue(x) {
  return x.take_profit ?? x.take_profit_price;
}

function fmtPriceOrUnset(value) {
  return value == null ? `<span class="muted">未设置</span>` : fmtMaybe(value);
}

function fmtPriceState(value, reason = "") {
  if (value != null && value !== "—") return fmtMaybe(value);
  if (reason === "non_trading_time") return `<span class="muted">非交易时段</span>`;
  if (reason === "roll_cooldown_block") return `<span class="muted">观察期阻断</span>`;
  if (reason === "halted_by_guard") return `<span class="muted">熔断阻断</span>`;
  if (String(reason).startsWith("risk_")) return `<span class="muted">风控阻断</span>`;
  if (reason === "blocked_by_pending_order") return `<span class="muted">pending 阻断</span>`;
  return `<span class="muted">未配置</span>`;
}

function symbolValue(obj, symbol) {
  return obj && typeof obj === "object" ? obj[symbol] : undefined;
}

function lifecycleStatusBar(rows) {
  const statuses = ["", "NEW", "SUBMITTED", "PARTIAL", "FILLED", "REJECTED", "EXPIRED", "CANCELED"];
  const counts = rows.reduce((acc, row) => {
    acc[row.status] = (acc[row.status] || 0) + 1;
    return acc;
  }, {});
  return `<div class="status-filter lifecycle-status-filter scroll-area">${statuses.map((status) => {
    const active = status === state.lifecycleStatusFilter;
    const label = status ? `${zhStatus(status)} ${fmtInt(counts[status] || 0)}` : `全部事件 ${fmtInt(rows.length)}`;
    return `<button class="filter-chip ${active ? "active" : ""}" data-lifecycle-status="${esc(status)}">${esc(label)}</button>`;
  }).join("")}</div>`;
}

function compactStatusBar(rows) {
  const statuses = ["NEW", "SUBMITTED", "PARTIAL", "FILLED", "CANCELED", "EXPIRED", "REJECTED"];
  const counts = rows.reduce((acc, row) => {
    acc[row.status] = (acc[row.status] || 0) + 1;
    return acc;
  }, {});
  return `<div class="status-filter compact-status-filter">${statuses.map((status) => `
    <button class="filter-chip" data-jump="lifecycle" title="${esc(status)}">${esc(zhStatus(status))} ${fmtInt(counts[status] || 0)}</button>
  `).join("")}</div>`;
}

function lifecycleReasonLabel(row) {
  const reason = zhReason(row.display_reason || row.reason);
  return row.folded_count ? `${reason} x${fmtInt(row.folded_count)}` : reason;
}

function rejectDonut(rejects) {
  const total = rejects.reduce((acc, item) => acc + Number(item.count || 0), 0);
  const colors = ["#ff4d47", "#ffb21a", "#27a7ff", "#7d8ca0"];
  return `<div class="donut-row">
    <div class="donut" data-total="${total}"></div>
    <div class="reason-list">
      ${rejects.length ? rejects.slice(0, 3).map((item, i) => `<div class="reason-item">
        <span class="reason-swatch" style="background:${colors[i % colors.length]}"></span>
        <span>${esc(zhReason(item.reason))}</span>
        <b>${fmtInt(item.count || 0)}</b>
      </div>`).join("") : `<div class="empty">暂无拒单</div>`}
    </div>
  </div>`;
}

function strategyTopNTable({ summary = false } = {}) {
  const rowsBySymbol = projectionStrategyRowsBySymbol();
  const rows = Object.entries(rowsBySymbol).map(([symbol, items]) => {
    const sorted = items.slice().sort((a, b) => Number(b.final_score || 0) - Number(a.final_score || 0));
    if (summary) {
      const top = sorted[0] || {};
      return [
        symbol,
        top.strategy_id || top.strategy_name || "—",
        `<span title="来自策略评分数据">${scoreCell(top.final_score)}</span>`,
        strategyEnabledLabel(symbol, top),
        switchRecommendationLabel(symbol, top),
      ];
    }
    return [symbol, ...[0, 1, 2].flatMap((idx) => {
      const item = sorted[idx] || {};
      return [
        item.strategy_id || item.strategy_name || "—",
        `<span title="来自策略评分数据">${scoreCell(item.final_score)}</span>`,
      ];
    })];
  });
  if (summary) {
    return table(["品种", "Top1 策略", "final_score", "当前启用", "推荐状态"], rows, {
      fit: true,
      className: "summary-table",
      colWidths: ["64px", "170px", "96px", "88px", "96px"],
    });
  }
  return table(["品种", "Top1 策略", "分数", "Top2 策略", "分数", "Top3 策略", "分数"], rows, { minWidth: "900px" });
}

function strategyEnabledLabel(symbol, top) {
  const enabled = projectionEnabledStrategies()?.[symbol] || [];
  const name = top.strategy_id || top.strategy_name;
  if (!name) return tag("未启用", "gray");
  return tag(enabled.includes(name) ? "已启用" : "未启用", enabled.includes(name) ? "green" : "gray");
}

function switchRecommendationLabel(symbol, top) {
  const sw = projectionStrategySwitch();
  const approved = sw.approved?.enabled_strategies_by_symbol?.[symbol] || sw.approved?.enabled?.[symbol] || [];
  const proposed = sw.proposal?.recommended_strategies_by_symbol?.[symbol] || sw.proposal?.enabled_strategies_by_symbol?.[symbol] || sw.proposal?.recommendations?.[symbol] || [];
  const name = top.strategy_id || top.strategy_name;
  if (name && Array.isArray(approved) && approved.includes(name)) return tag("已晋升", "green");
  if (name && Array.isArray(proposed) && proposed.includes(name)) return tag("推荐", "blue");
  if (sw.state === "disabled" || sw.state === "not_applicable") return tag("未晋升", "gray");
  return tag(sw.approved ? "未推荐" : "待晋升", sw.approved ? "gray" : "yellow");
}

function strategySwitchStatePanel(sw) {
  const labelByState = {
    not_applicable: "不适用",
    disabled: "等待策略评分",
    proposal_pending: "等待自动晋升",
    approved: "已自动晋升",
    rejected: "已拒绝",
  };
  const toneByState = {
    not_applicable: "gray",
    disabled: "blue",
    proposal_pending: "yellow",
    approved: "green",
    rejected: "red",
  };
  const stateValue = sw.state || "not_applicable";
  return table(["项目", "当前状态"], [
    ["状态", tag(labelByState[stateValue] || stateValue, toneByState[stateValue] || "gray")],
    ["晋升模式", sw.approval_required ? "等待提案" : "自动晋升"],
    ["原因", zhReason(sw.state_reason) || sw.state_reason || "—"],
  ], { fit: true });
}

function switchProposalPanel(sw) {
  if (sw.state === "disabled") return `<div class="empty">等待策略评分产出后自动晋升。</div>`;
  if (sw.state === "not_applicable") return `<div class="empty">当前模式不适用策略切换。</div>`;
  return jsonPanel("switchProposal", sw.proposal || {});
}

function switchApprovalPanel(sw) {
  if (sw.state === "disabled") return `<div class="empty">自动晋升等待策略评分；无需操作。</div>`;
  if (sw.state === "not_applicable") return `<div class="empty">当前模式不适用策略切换。</div>`;
  if (sw.state === "approved") {
    return jsonPanel("switchApproved", sw.approved || { state: sw.state, note: "已自动晋升。" });
  }
  if (sw.state === "rejected") {
    return jsonPanel("switchRejected", sw.rejected || { state: sw.state, note: "已发现 rejected artifact。" });
  }
  const proposal = sw.proposal || {};
  const hasProposal = Boolean(Object.keys(proposal).length);
  const recommended = proposal.enabled_strategies_by_symbol || {};
  const current = proposal.current_enabled_by_symbol || {};
  const rows = Object.keys({ ...current, ...recommended }).sort().map((symbol) => [
    symbol,
    Array.isArray(current[symbol]) ? current[symbol].join(" / ") : "—",
    Array.isArray(recommended[symbol]) ? recommended[symbol].join(" / ") : "—",
    proposal.symbols?.[symbol]?.switch_required ? tag("需要切换", "yellow") : tag("保持", "green"),
  ]);
  return `
    <div class="approval-panel">
      ${table(["品种", "当前生效", "自动晋升策略", "变更"], rows, { fit: true, emptyMessage: "暂无可晋升提案。" })}
      <div class="approval-actions">
        <span class="muted">${hasProposal ? "系统会根据 final_score 自动写入 approved artifact；当前运行 session 不做热切换，下次启动生效。" : "等待策略评分后生成自动晋升提案。"}</span>
      </div>
    </div>
  `;
}

function gatesTable(activeSymbols, enabled, { summary = false } = {}) {
  const rows = candidateRows(activeSymbols, enabled).map((r) => [
    r.symbol,
    r.contract,
    tag(r.activeLabel, r.activeTone),
    tag(r.tradeLabel, r.tradeTone),
    r.strategy,
    `<span title="raw=${esc(r.raw)} cost=${esc(r.cost)} risk=${esc(r.risk)}">${scoreCell(r.final)}</span>`,
    r.direction,
    r.latestMarketPrice,
    r.orderPrice,
    r.executionPrice,
    r.stopLoss,
    r.takeProfit,
    r.position,
    tag(r.gateStatus, r.gateTone),
    r.blockReason,
    r.nextAction,
  ]);
  const headers = ["品种", "合约", "是否活跃", "是否可交易", "当前策略", "final_score", "开仓方向", "最新行情价", "委托价", "成交价", "止损价", "止盈价", "持仓状态", "执行门控状态", "阻断原因", "下一步动作"];
  const tableOptions = summary
    ? { minWidth: "1860px", className: "summary-table" }
    : { minWidth: "1860px" };
  return `
    <div class="gate-legend" style="height:30px; align-items:center;">
      <span><i class="legend-dot" style="background:var(--green)"></i>可开仓</span>
      <span><i class="legend-dot" style="background:var(--blue)"></i>等待触发</span>
      <span><i class="legend-dot" style="background:var(--yellow)"></i>门控阻断</span>
      <span><i class="legend-dot" style="background:var(--red)"></i>熔断/限频</span>
      <span><i class="legend-dot" style="background:#7d8ca0"></i>非交易时段</span>
    </div>
    ${table(headers, rows, tableOptions)}
  `;
}

function candidateRows(activeSymbols, enabled) {
  const quoteSymbols = projectionItems("quotes").map((item) => item.symbol).filter(Boolean);
  const symbols = [...new Set([...quoteSymbols, ...Object.keys(enabled || {}), ...(activeSymbols || [])])];
  const activeSet = new Set(activeSymbols || []);
  const usesTopN = topNEnabled();
  const scores = Object.values(projectionStrategyRowsBySymbol()).flat();
  const latestBySymbol = {};
  scores.forEach((s) => {
    const sym = s.symbol || "—";
    if (!latestBySymbol[sym] || Number(s.final_score || 0) > Number(latestBySymbol[sym].final_score || 0)) {
      latestBySymbol[sym] = s;
    }
  });
  const pendingBySymbol = {};
  projectionItems("pending_orders").forEach((item) => {
    if (item.symbol) pendingBySymbol[item.symbol] = item;
  });
  const positionsBySymbol = {};
  projectionItems("positions").forEach((item) => {
    if (!item.symbol) return;
    positionsBySymbol[item.symbol] ||= [];
    positionsBySymbol[item.symbol].push(item);
  });
  return symbols.map((symbol) => {
    const score = latestBySymbol[symbol] || {};
    const pending = pendingBySymbol[symbol] || {};
    const positions = positionsBySymbol[symbol] || [];
    const active = usesTopN ? activeSet.has(symbol) : true;
    const reason = pending.reason || "";
    const blocked = Boolean(pending.order_id);
    const quote = quoteFor(symbol, pending.trade_instrument_id || positions[0]?.trade_instrument_id);
    const tradeState = quote?.tradability?.state || "unknown";
    const isTradable = tradeState === "tradable";
    const tradeLabel = tradeState === "tradable" ? "交易中" : tradeState === "non_trading_time" ? "非交易时段" : "状态未知";
    const tradeTone = tradeState === "tradable" ? "green" : tradeState === "non_trading_time" ? "yellow" : "gray";
    const contract = pending.trade_instrument_id || positions[0]?.trade_instrument_id || quote?.trade_instrument_id || "—";
    return {
      symbol,
      contract,
      active,
      activeLabel: usesTopN ? (active ? "活跃" : "未活跃") : "未启用 TopN",
      activeTone: usesTopN ? (active ? "green" : "gray") : "blue",
      tradable: isTradable,
      tradeLabel,
      tradeTone,
      strategy: (enabled[symbol] || [score.strategy_id || score.strategy_name || "—"]).join(" / "),
      final: score.final_score ?? "—",
      raw: score.raw_score ?? "—",
      cost: score.cost_penalty ?? "—",
      risk: score.risk_penalty ?? "—",
      direction: pending.side ? sideZh(pending.side) : decisionDirectionZh(score.decision),
      latestMarketPrice: quote?.latest_market_price == null ? `<span class="muted">${esc(quoteUnavailableLabel(quote))}</span>` : fmtMaybe(quote.latest_market_price),
      orderPrice: quote?.order_price == null ? `<span class="muted">委托价未记录</span>` : fmtMaybe(quote.order_price),
      executionPrice: quote?.last_execution_price == null ? `<span class="muted">暂无成交价</span>` : fmtMaybe(quote.last_execution_price),
      stopLoss: fmtPriceOrUnset(quote?.stop_loss),
      takeProfit: fmtPriceOrUnset(quote?.take_profit),
      position: positions.length ? positions.map((pos) => `${positionZh(pos.position_side)} ${fmtMaybe(pos.quantity)}`).join(" / ") : "空仓",
      gateStatus: blocked ? "待成交/挂单" : active && isTradable ? "可开仓" : "等待",
      gateTone: blocked ? (String(reason).startsWith("risk_") || reason === "halted_by_guard" ? "red" : "yellow") : active && isTradable ? "green" : "blue",
      blockReason: reason ? zhReason(reason) : "—",
      nextAction: blocked ? "等待订单终态" : quote?.tradability?.next_action || (active && isTradable ? "等待价格触发" : "等待交易状态确认"),
    };
  });
}

function renderRun() {
  $("view-run").innerHTML = `<div class="subpage-grid">
    ${card("运行概览", overviewTiles(), { height: "h320" })}
    ${card("事件统计", eventStatsTable(), { height: "h320" })}
    ${card("Manifest / Warnings", jsonPanel("manifestWarnings", { alerts: projection()?.alerts || {}, warnings: state.dashboard.warnings, optional_warnings: state.dashboard.optional_warnings, manifest: state.dashboard.manifest }), { height: "h-json" })}
    ${card("Plan 摘要", jsonPanel("planSummary", state.dashboard.plan), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderPortfolio() {
  $("view-portfolio").innerHTML = `<div class="subpage">
    ${card("组合资金指标", portfolioTable(), { height: "h320" })}
    ${card("持仓与关键价格", positionsTable(), { height: "h360" })}
    ${card("待成交 / 挂单", pendingOrdersTable(), { height: "h360" })}
  </div>`;
}

function renderLifecycle() {
  const allRows = projectionScope("lifecycle_view").items || currentTails().order_lifecycle_events || [];
  const rows = state.lifecycleStatusFilter ? allRows.filter((x) => x.status === state.lifecycleStatusFilter) : allRows;
  $("view-lifecycle").innerHTML = `<div class="subpage">
    ${card(scopedTitle("订单生命周期事件日志"), `${lifecycleStatusBar(allRows)}${lifecycleTable(rows)}`, { height: "h-full" })}
  </div>`;
  wireLifecycleFilters();
}

function renderRisk() {
  const riskSummary = projection()?.risk_summary?.[currentScope()] || {};
  $("view-risk").innerHTML = `<div class="subpage-grid">
    ${card("风控拒单统计", rejectDonut(riskSummary.top_risk_reject_reasons || []), { height: "h320" })}
    ${card("关键阻断 reason", riskReasonBreakdown(), { height: "h320" })}
    ${card("Risk Stats", jsonPanel("riskStats", riskSummary), { height: "h-json" })}
    ${card("风控配置", jsonPanel("riskConfig", planConfig().risk || {}), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderSwitch() {
  const sw = projectionStrategySwitch();
  $("view-switch").innerHTML = `<div class="subpage-grid">
    ${card("自动晋升状态", strategySwitchStatePanel(sw), { height: "h260" })}
    ${card("策略评分 TopN（含成本/风险惩罚）", strategyScoreDecisionTable(), { height: "h320" })}
    ${card("当前生效 / 推荐 / 晋升", switchSummaryTable(sw), { height: "h320" })}
    ${card("切换提案", switchProposalPanel(sw), { height: "h-json" })}
    ${card("自动晋升结果", switchApprovalPanel(sw), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderGates() {
  $("view-gates").innerHTML = `<div class="subpage">
    ${card("候选开仓与执行门控（关键机会与阻断原因）", gatesTable(activeSymbolsForDisplay(), projectionEnabledStrategies()), { height: "h360" })}
  </div>`;
}

function renderRoll() {
  $("view-roll").innerHTML = `<div class="subpage-grid">
    ${card("模式 B 阶段", rollStageTable(), { height: "h320" })}
    ${card("换月流程条件", rollConditionTable(), { height: "h320" })}
    ${card("roll_events 时间线", rollEventsTable(), { height: "h320" })}
    ${card("相关 lifecycle reason", lifecycleTable((currentTails().order_lifecycle_events || []).filter((x) => String(x.reason || "").startsWith("roll_"))), { height: "h320" })}
  </div>`;
}

function renderMarket() {
  $("view-market").innerHTML = `<div class="subpage-grid">
    ${card("合约与行情", contractsTable(), { height: "h320" })}
    ${card("活跃品种", rankTable(), { height: "h320" })}
    ${card("合约规格与行情配置", jsonPanel("marketConfig", { instruments: planConfig().instruments, market_data: planConfig().adapters?.market_data }), { height: "h-json" })}
    ${card("行情状态 JSON", jsonPanel("quoteProjectionRaw", projectionScope("quotes")), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderLogs() {
  $("view-logs").innerHTML = `<div class="subpage-grid">
    ${card("事件时间线", timelineTable(), { height: "h420" })}
    ${card("原始 Dashboard JSON", jsonPanel("dashboardRaw", state.dashboard || {}), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderConfig() {
  $("view-config").innerHTML = `<div class="subpage">
    ${card("配置摘要", configSummaryTable(), { height: "h260" })}
    ${card("配置 JSON（只读）", jsonPanel("planConfigRaw", planConfig()), { height: "h-json" })}
  </div>`;
  wireJsonPanels();
}

function renderAlerts() {
  $("view-alerts").innerHTML = `<div class="subpage-grid">
    ${card("告警中心", alertsList(), { height: "h360" })}
    ${card("数据提示 / 可选产物状态", optionalWarningsTable(), { height: "h360" })}
  </div>`;
  wireAlertLinks();
}

function renderPermissions() {
  $("view-permissions").innerHTML = card("权限管理（只读）", table(["项目", "状态", "说明"], [
    ["Web UI", tag("只读", "blue"), "当前页面不执行写操作"],
    ["策略切换", tag("自动晋升", "green"), "系统根据策略评分自动生成 approved artifact"],
    ["实盘提交", tag("Hard Gate", "red"), "live submit 需要 confirm_live 与 runtime_id token"],
  ]), { height: "h260" });
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
    ["active_top_n", topNEnabled() ? plan.runtime?.active_top_n : "N/A（未启用 TopN）"],
    ["active_symbols", activeSymbolsLabel()],
    ["universe", (plan.universe?.symbols || []).join(", ")],
  ]);
}

function overviewTiles() {
  const plan = planConfig();
  const execution = state.dashboard.execution || {};
  const optionalWarnings = projection()?.alerts?.optional_warnings || [];
  const items = [
    ["runtime_id", state.dashboard.runtime_id],
    ["模式", zhMode(plan.runtime?.mode || plan.adapters?.market_data?.mode)],
    ["Broker", execution.broker_type || "—"],
    ["执行模式", zhMode(execution.execution_mode)],
    ["真实确认", execution.confirm_live ? "是" : "否"],
    ["TopN", topNEnabled() ? `启用 Top ${plan.runtime?.active_top_n}` : "未启用"],
    ["活跃品种", activeSymbolsLabel()],
    ["Universe", (plan.universe?.symbols || []).join(", ")],
    ["Alerts", (projection()?.alerts?.items || []).map((x) => zhReason(x.code)).join(" / ") || "—"],
    ["可选产物提示", optionalWarnings.map((x) => zhWarning(x.code)).join(" / ") || "—"],
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
  const s = currentStats();
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
  const p = latestPortfolio();
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

function configSummaryTable() {
  const plan = planConfig();
  return table(["配置项", "当前值", "说明"], [
    ["运行模式", zhMode(plan.runtime?.mode || plan.adapters?.market_data?.mode), "由 runtime.mode 或 market_data.mode 推导"],
    ["Universe", (plan.universe?.symbols || []).join(", ") || "未配置", "策略层 base symbols"],
    ["TopN", topNEnabled() ? `启用 Top ${plan.runtime?.active_top_n}` : "未启用", "未启用时不产生 rank_events"],
    ["Broker", plan.adapters?.broker?.mode || "simulated", "执行适配器模式"],
    ["MarketData", plan.adapters?.market_data?.mode || "—", "行情适配器模式"],
    ["Risk", plan.risk ? "已配置" : "未配置", "缺省表示未启用额外阈值"],
  ], { fit: true });
}

function reasonsTable(rows) {
  return table(["reason", "中文", "次数"], rows.map((x) => [x.reason || "—", zhReason(x.reason), fmtInt(x.count || 0)]));
}

function riskReasonBreakdown() {
  const reasons = projection()?.risk_summary?.[currentScope()]?.top_risk_reject_reasons || [];
  const byReason = Object.fromEntries(reasons.map((x) => [x.reason, x.count || 0]));
  const keys = ["risk_max_notional", "risk_max_risk_ratio", "risk_max_margin_used", "rate_limited", "halted_by_guard", "blocked_by_pending_order"];
  return table(["英文 reason", "中文", "次数", "说明"], keys.map((key) => [
    key,
    zhReason(key),
    fmtInt(byReason[key] || 0),
    key.startsWith("risk_") ? "风控阈值拒单" : key === "rate_limited" ? "下单频率保护" : key === "halted_by_guard" ? "连续拒绝触发熔断" : "未终态订单阻塞",
  ]), { minWidth: "780px" });
}

function projectionStrategyRowsBySymbol() {
  const proposal = projectionStrategySwitch().proposal || {};
  const ranked = proposal.symbols || proposal.symbol_scores || [];
  const enabled = projectionEnabledStrategies();
  const out = {};
  const scoreRows = projectionStrategyScores().latest_by_symbol || {};
  Object.entries(scoreRows).forEach(([symbol, items]) => {
    if (Array.isArray(items) && items.length) {
      out[symbol] = items.map((item) => ({
        symbol,
        strategy_id: item.strategy_id || item.strategy_name,
        strategy_name: item.strategy_name || item.strategy_id,
        final_score: item.final_score,
        raw_score: item.raw_score,
        cost_penalty: item.cost_penalty,
        risk_penalty: item.risk_penalty,
        decision: item.decision,
        strength: item.strength,
        confidence: item.confidence,
      }));
    }
  });
  if (Array.isArray(ranked)) {
    ranked.forEach((item) => {
      if (!item || typeof item !== "object") return;
      const symbol = item.symbol || "—";
      const strategies = item.ranked_strategies || item.strategies || [];
      if (Array.isArray(strategies) && strategies.length) {
        out[symbol] ||= strategies.map((strategy) => ({
          symbol,
          strategy_id: strategy.strategy_id || strategy.strategy_name || strategy.name,
          strategy_name: strategy.strategy_name || strategy.strategy_id || strategy.name,
          final_score: strategy.final_score ?? strategy.score,
          raw_score: strategy.raw_score,
          cost_penalty: strategy.cost_penalty,
          risk_penalty: strategy.risk_penalty,
          decision: strategy.decision,
          strength: strategy.strength,
          confidence: strategy.confidence,
        }));
      }
    });
  } else if (ranked && typeof ranked === "object") {
    Object.entries(ranked).forEach(([symbol, item]) => {
      const strategies = item?.ranked_strategies || item?.strategies || [];
      if (Array.isArray(strategies) && strategies.length) {
        out[symbol] ||= strategies.map((strategy) => ({
          symbol,
          strategy_id: strategy.strategy_id || strategy.strategy_name || strategy.name,
          strategy_name: strategy.strategy_name || strategy.strategy_id || strategy.name,
          final_score: strategy.final_score ?? strategy.score,
          raw_score: strategy.raw_score,
          cost_penalty: strategy.cost_penalty,
          risk_penalty: strategy.risk_penalty,
          decision: strategy.decision,
          strength: strategy.strength,
          confidence: strategy.confidence,
        }));
      }
    });
  }
  Object.entries(enabled).forEach(([symbol, names]) => {
    if (out[symbol]) return;
    out[symbol] = (Array.isArray(names) ? names : []).map((name) => ({
      symbol,
      strategy_id: name,
      strategy_name: name,
      final_score: null,
    }));
  });
  return out;
}

function enabledStrategiesTable() {
  const enabled = projectionEnabledStrategies();
  return table(["品种", "启用策略"], Object.entries(enabled).map(([sym, names]) => [sym, Array.isArray(names) ? names.join(" / ") : "—"]));
}

function strategyScoreDecisionTable() {
  const enabled = projectionEnabledStrategies();
  const approved = projectionStrategySwitch()?.approved || {};
  const approvedSymbols = approved.enabled_strategies_by_symbol || approved.enabled || {};
  const rows = Object.values(projectionStrategyRowsBySymbol()).flat()
    .slice()
    .sort((a, b) => Number(b.final_score || 0) - Number(a.final_score || 0))
    .slice(0, 80)
    .map((item) => {
      const symbol = item.symbol || "—";
      const strategy = item.strategy_id || item.strategy_name || "—";
      const enabledList = enabled[symbol] || [];
      const approvedList = approvedSymbols[symbol] || [];
      return [
        symbol,
        strategy,
        scoreCell(item.final_score),
        fmtMaybe(item.raw_score),
        fmtMaybe(item.cost_penalty),
        fmtMaybe(item.risk_penalty),
        tag(enabledList.includes(strategy) ? "已启用" : "未启用", enabledList.includes(strategy) ? "green" : "gray"),
        tag(approvedList.includes(strategy) ? "已晋升" : "未晋升", approvedList.includes(strategy) ? "green" : "yellow"),
      ];
    });
  return table(["品种", "策略", "final_score", "raw_score", "cost_penalty", "risk_penalty", "当前启用", "晋升状态"], rows, { minWidth: "1160px" });
}

function switchSummaryTable(sw) {
  const enabled = projectionEnabledStrategies();
  const proposal = sw.proposal || {};
  const approved = sw.approved || {};
  const recommended = proposal.recommended_strategies_by_symbol || proposal.enabled_strategies_by_symbol || {};
  const currentFromProposal = proposal.current_enabled_by_symbol || {};
  const approvedSet = approved.enabled_strategies_by_symbol || approved.enabled || {};
  const symbols = new Set([...Object.keys(enabled), ...Object.keys(currentFromProposal), ...Object.keys(recommended), ...Object.keys(approvedSet)]);
  return table(["品种", "当前生效策略", "推荐策略", "是否已晋升", "原因"], [...symbols].map((symbol) => [
    symbol,
    Array.isArray(currentFromProposal[symbol]) ? currentFromProposal[symbol].join(" / ") : Array.isArray(enabled[symbol]) ? enabled[symbol].join(" / ") : "—",
    Array.isArray(recommended[symbol]) ? recommended[symbol].join(" / ") : "—",
    tag(approvedSet[symbol] ? "已晋升" : "未晋升", approvedSet[symbol] ? "green" : "yellow"),
    proposal.symbols?.[symbol]?.switch_required ? "推荐切换" : proposal.reason || proposal.threshold_reason || "按 final_score 排序",
  ]), { minWidth: "960px" });
}

function rollStageTable() {
  const rollEvents = currentTails().roll_events || [];
  const lifecycle = currentTails().order_lifecycle_events || [];
  const last = rollEvents[rollEvents.length - 1] || {};
  const hasCancel = lifecycle.some((x) => x.reason === "roll_cancel_pending");
  const hasClose = lifecycle.some((x) => x.reason === "roll_close_position");
  const cooldown = lifecycle.filter((x) => x.reason === "roll_cooldown_block").length;
  const stages = [
    ["撤单中（Cancel Pending）", last.from_contract || "—", last.to_contract || "—", fmtEventTime(last.event_time ?? last.created_at ?? last.ts), hasCancel ? "完成" : "无 pending", hasCancel ? "roll_cancel_pending" : "—"],
    ["清仓中（Close Position）", last.from_contract || "—", last.to_contract || "—", fmtEventTime(last.event_time ?? last.created_at ?? last.ts), hasClose ? "完成" : "无旧仓位", hasClose ? "roll_close_position" : "—"],
    ["观察中（Cooldown）", last.from_contract || "—", last.to_contract || "—", fmtEventTime(last.event_time ?? last.created_at ?? last.ts), cooldown ? `剩余/阻断 ${cooldown} 次` : "未进入/已结束", "roll_cooldown_block"],
    ["就绪（Ready）", last.from_contract || "—", last.to_contract || "—", fmtEventTime(last.event_time ?? last.created_at ?? last.ts), last.to_contract ? "已切换" : "等待换月", last.to_contract || "—"],
    ["重新开仓（Re-Entry）", last.from_contract || "—", last.to_contract || "—", fmtEventTime(last.event_time ?? last.created_at ?? last.ts), latestNewContractOrder(last.to_contract) ? "已恢复" : "等待条件", last.to_contract || "—"],
  ];
  return table(["阶段", "旧合约", "新合约", "触发时间", "当前状态", "观察条件 / reason"], stages, { minWidth: "1060px" });
}

function rollEventsTable() {
  return table(["触发时间/tick", "品种", "旧合约", "新合约", "当前阶段", "剩余观察 tick", "允许再开仓条件"], (currentTails().roll_events || []).map((x) => [
    fmtEventTime(x.event_time ?? x.created_at ?? x.ts),
    x.base_symbol || "—",
    x.from_contract || "—",
    x.to_contract || "—",
    "观察中 / 就绪",
    "由 cooldown_ticks 控制",
    "仓位=0 且无 pending 且观察期结束",
  ]), { minWidth: "1120px", emptyMessage: "暂无换月事件；需要 fixed_main 且发生主力切换后才会产生 roll_events。" });
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
  const rows = projectionItems("quotes").map((item) => [
    item.symbol || "—",
    item.trade_instrument_id || "—",
    item.latest_market_price == null ? `<span class="muted">${esc(quoteUnavailableLabel(item))}</span>` : fmtMaybe(item.latest_market_price),
    item.last_execution_price == null ? `<span class="muted">暂无成交价</span>` : fmtMaybe(item.last_execution_price),
    item.order_price == null ? `<span class="muted">委托价未记录</span>` : fmtMaybe(item.order_price),
    zhPriceSource(item.price_source),
    zhPriceSource(item.execution_price_source),
    zhReason(item.reason),
  ]);
  return table(["品种", "执行合约", "最新行情价", "最近成交价", "委托价", "行情来源", "成交价来源", "状态"], rows, {
    minWidth: "1080px",
    emptyMessage: "暂无行情/合约数据。",
  });
}

function rankTable() {
  const active = projectionScope("active_symbols");
  return table(["活跃品种", "来源", "说明"], [[
    (active.symbols || []).join(", ") || "—",
    zhProjectionSource(active.source),
    active.source === "strategy_switch_proposal"
      ? "未记录排名事件，使用策略切换提案中的活跃品种。"
      : active.source === "universe"
        ? "未启用 TopN，使用完整品种池。"
        : "使用运行中记录的活跃品种。",
  ]], { emptyMessage: "暂无活跃品种数据。" });
}

function optionalWarningsTable() {
  const rows = (projection()?.alerts?.optional_warnings || []).map((item) => [
    zhWarning(String(item.code || "").split(":")[0]),
    item.level === "info" ? "提示" : item.level || "提示",
    item.message && item.message !== item.code ? item.message : zhWarning(String(item.code || "").split(":")[0]),
    item.source === "artifact" ? "可选产物" : "运行数据",
  ]);
  return table(["项目", "级别", "说明", "来源"], rows, {
    minWidth: "760px",
    emptyMessage: "暂无可选产物提示。",
  });
}

function timelineTable() {
  const tail = currentTails();
  const rows = [
    ...(tail.order_lifecycle_events || []),
    ...(tail.rank_events || []),
    ...(tail.strategy_score_events || []),
    ...(tail.roll_events || []),
  ].sort((a, b) => Number(a.ts || 0) - Number(b.ts || 0));
  return table(["时间/tick", "类型", "品种", "状态", "原因"], rows.map((x) => [
    fmtEventTime(x.event_time ?? x.created_at ?? x.ts),
    x.event_type || "—",
    x.symbol || x.base_symbol || x.instrument_id || "—",
    zhStatus(x.status),
      lifecycleReasonLabel(x),
  ]));
}

function table(headers, rows, { minWidth = "100%", fit = false, emptyMessage = "暂无数据", className = "", colWidths = [] } = {}) {
  const colgroup = colWidths.length
    ? `<colgroup>${colWidths.map((width) => `<col style="width:${esc(width)}">`).join("")}</colgroup>`
    : "";
  return `<div class="table-wrap scroll-area ${fit ? "no-x" : ""}"><table class="data-table ${className} ${fit ? "fit-table" : ""}" style="--table-min:${esc(minWidth)}">
    ${colgroup}
    <thead><tr>${headers.map((h) => `<th>${esc(h)}</th>`).join("")}</tr></thead>
    <tbody>${rows.length ? rows.map((row) => `<tr>${row.map((cell) => `<td title="${titleText(cell)}">${cell == null ? "—" : cell}</td>`).join("")}</tr>`).join("") : `<tr><td colspan="${headers.length}"><div class="empty">${esc(emptyMessage)}</div></td></tr>`}</tbody>
  </table></div>`;
}

function latestScores() {
  return currentTails().strategy_score_events || [];
}

function latestScoreSnapshot() {
  const rows = latestScores();
  if (!rows.length) return [];
  const maxTs = rows.reduce((acc, row) => {
    const ts = Number(row.ts ?? row.tick ?? 0);
    return Number.isFinite(ts) && ts > acc ? ts : acc;
  }, -Infinity);
  return rows.filter((row) => Number(row.ts ?? row.tick ?? 0) === maxTs);
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

function decisionDirectionZh(decision) {
  if (decision === "OPEN_LONG") return "多";
  if (decision === "OPEN_SHORT") return "空";
  if (decision === "CLOSE_LONG") return "平多";
  if (decision === "CLOSE_SHORT") return "平空";
  if (decision === "HOLD") return "观望";
  return decision || "—";
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
  return (currentTails().order_events || []).some((x) => x.trade_instrument_id === contract);
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
