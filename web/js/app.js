// app.js: pide los datos (JSON) y pinta el dashboard.
// No calcula estrategias ni opera: solo muestra lo que le manda el bot.
(function () {
  "use strict";

  const CFG = window.APP_CONFIG || { dataUrl: "data/dashboard.json", refreshSeconds: 0 };
  const $ = (id) => document.getElementById(id);
  let DATA = null;
  let chart = null;
  let range = 0;          // días visibles en la gráfica (0 = todo)
  let selectedLevel = null;

  // ---------- Formato de números (USD, estilo español) ----------
  // Formato español (1.014,82) con el símbolo $ delante, para que se vea claro que son dólares.
  const num = (v, d = 2) => new Intl.NumberFormat("es-ES", { minimumFractionDigits: d, maximumFractionDigits: d, useGrouping: "always" }).format(v);
  const usd = { format: (v) => (v < 0 ? "−" : "") + "$" + num(Math.abs(v), 2) };
  const signed = (v, fmt) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v));
  const money = (v) => signed(v, usd.format);
  const pct = (v, d = 2) => signed(v, (x) => num(x, d) + " %");
  const cls = (v) => (v > 0 ? "gain" : v < 0 ? "loss" : "");
  const price = (v) => (v >= 1000 ? num(v, 0) : num(v, 2));
  const fdate = (iso, withTime) => {
    const d = new Date(iso);
    const opts = withTime
      ? { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" }
      : { day: "2-digit", month: "short", year: "numeric" };
    return d.toLocaleString("es-ES", opts);
  };
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ---------- Carga de datos ----------
  async function load() {
    try {
      const res = await fetch(CFG.dataUrl, { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
      $("load-error").hidden = true;
      render();
    } catch (err) {
      const box = $("load-error");
      box.hidden = false;
      box.innerHTML = location.protocol === "file:"
        ? "<strong>No se pueden leer los datos abriendo el archivo con doble clic.</strong> El navegador bloquea leer archivos locales. Abre una terminal en la carpeta de la web, ejecuta <code>python3 -m http.server 8000</code> y entra en http://localhost:8000"
        : "<strong>No se han podido cargar los datos</strong> desde " + esc(CFG.dataUrl) + " (" + esc(err.message) + "). La web volverá a intentarlo sola.";
      $("bot-status").textContent = "Sin datos";
      $("bot-status").className = "pill pill-bad";
    }
  }

  function render() {
    renderHeader();
    renderKpis();
    renderAggressiveness();
    renderChart();
    renderLearning();
    renderPositions();
    renderTrades();
    renderLogs();
    renderLimits();
  }

  // ---------- Estado y avisos ----------
  function renderHeader() {
    const m = DATA.meta, brake = DATA.emergency_brake, st = DATA.stats;
    const status = $("bot-status");
    const labels = { running: ["Bot activo", "pill-ok"], paused: ["Bot en pausa", "pill-bad"], stopped: ["Bot detenido", "pill-bad"] };
    const [txt, c] = brake.active ? ["Freno activado", "pill-bad"] : (labels[m.bot_status] || [m.bot_status, ""]);
    status.textContent = txt;
    status.className = "pill " + c;
    $("updated").textContent = "Actualizado " + fdate(m.generated_at, true);
    $("sample-note").textContent = m.is_sample_data
      ? "Ahora mismo se muestran DATOS DE PRUEBA inventados. Cuando el bot esté conectado, esta nota desaparecerá."
      : "Estrategia: " + m.strategy + (m.started_at ? " · cartera iniciada el " + fdate(m.started_at, true) + " con " + usd.format(DATA.account.initial_capital) : "");

    const bb = $("brake-banner");
    bb.hidden = !brake.active;
    if (brake.active) {
      bb.innerHTML = "<strong>Freno de emergencia activado</strong> el " + fdate(brake.triggered_at, true) +
        ": la cartera cayó un " + DATA.risk_limits.emergency_brake_drawdown_pct + " % desde su máximo. El bot no abre operaciones nuevas hasta que lo reactives.";
    }

    const diff = st.return_pct - st.benchmark_return_pct;
    const bn = $("bench-banner");
    bn.hidden = diff >= 0;
    if (diff < 0) {
      bn.innerHTML = "<strong>El bot va por detrás del índice.</strong> Rentabilidad del bot " + pct(st.return_pct) +
        " frente a " + pct(st.benchmark_return_pct) + " de " + esc(m.benchmark.name) +
        ". Ahora mismo habría ganado más comprando y manteniendo el índice.";
    }
  }

  // ---------- 1. Cifras principales ----------
  function renderKpis() {
    const a = DATA.account, s = DATA.stats, b = DATA.meta.benchmark;
    $("kpi-balance").textContent = usd.format(a.balance);
    $("kpi-balance-sub").textContent = "Inicial " + usd.format(a.initial_capital) + " · liquidez " + usd.format(a.cash);

    const pnl = $("kpi-pnl");
    pnl.textContent = money(s.total_pnl);
    pnl.className = "kpi-value " + cls(s.total_pnl);
    $("kpi-pnl-sub").innerHTML = '<span class="' + cls(s.return_pct) + '">' + pct(s.return_pct) + "</span> · comisiones " + usd.format(s.fees_paid);

    const diff = s.return_pct - s.benchmark_return_pct;
    $("kpi-bench-label").textContent = "Frente a " + b.symbol;
    const kb = $("kpi-bench");
    kb.textContent = signed(diff, (x) => num(x, 2)) + " pp";
    kb.className = "kpi-value " + cls(diff);
    $("kpi-bench-sub").textContent = "Bot " + pct(s.return_pct) + " · índice " + pct(s.benchmark_return_pct);

    $("kpi-win").textContent = num(s.win_rate_pct, 1) + " %";
    $("kpi-win-sub").textContent = s.wins + " ganadas · " + s.losses + " perdidas de " + s.trades_closed;
  }

  // ---------- 2. Agresividad ----------
  // Pérdida máxima esperada = peor caso en que TODAS las posiciones abiertas tocan su stop a la vez,
  // sumando comisión y deslizamiento de entrada y salida.
  function worstLoss(lv) {
    const r = DATA.risk_limits;
    const costs = 2 * (r.fee_pct_per_side + r.slippage_pct_per_side);
    const invested = lv.position_size_pct * lv.max_open_trades;
    return { invested, lossPct: invested * (lv.stop_loss_pct + costs) / 100 };
  }
  function checkLimits(lv) {
    const r = DATA.risk_limits, { invested } = worstLoss(lv);
    const problems = [];
    if (lv.position_size_pct > r.max_per_asset_pct) problems.push("supera el " + r.max_per_asset_pct + " % por activo");
    if (invested > 100 - r.min_cash_pct) problems.push("deja menos del " + r.min_cash_pct + " % en liquidez");
    if (!(lv.stop_loss_pct > 0)) problems.push("no tiene stop-loss");
    return problems;
  }

  function renderAggressiveness() {
    const ag = DATA.aggressiveness;
    if (!selectedLevel) selectedLevel = ag.current;
    const box = $("aggr-levels");
    box.innerHTML = "";
    ag.levels.forEach((lv, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("role", "radio");
      b.setAttribute("aria-checked", String(lv.id === selectedLevel));
      b.id = "lvl-" + lv.id;
      let bars = "";
      for (let k = 0; k < ag.levels.length; k++) bars += '<i class="' + (k <= i ? "on" : "") + '" style="height:' + (4 + k * 1.5) + 'px"></i>';
      b.innerHTML = '<span class="bars">' + bars + "</span><span>" + esc(lv.name) + "</span>" +
        (lv.id === ag.current ? '<span class="cur">actual</span>' : "");
      b.addEventListener("click", () => { selectedLevel = lv.id; renderAggressiveness(); });
      box.appendChild(b);
    });

    const lv = ag.levels.find((l) => l.id === selectedLevel) || ag.levels[0];
    const cap = DATA.account.balance, r = DATA.risk_limits;
    const { invested, lossPct } = worstLoss(lv);
    $("lv-size").textContent = lv.position_size_pct + " % (" + usd.format(cap * lv.position_size_pct / 100) + ")";
    $("lv-stop").textContent = "−" + lv.stop_loss_pct + " %";
    $("lv-max").textContent = lv.max_open_trades;
    $("lv-inv").textContent = invested + " % / " + (100 - invested) + " %";
    $("lv-loss").textContent = "−" + usd.format(cap * lossPct / 100) + " (−" + num(lossPct, 1) + " %)";
    const brake = r.emergency_brake_drawdown_pct;
    $("lv-meter").style.width = Math.min(100, (lossPct / (brake * 1.2)) * 100) + "%";
    $("lv-brake-mark").style.left = (100 / 1.2) + "%";
    $("lv-loss-note").textContent = "Si todas las posiciones abiertas tocaran su stop a la vez, con comisiones y deslizamiento. La raya blanca es el freno de emergencia (−" + brake +
      " %). Un hueco de precio (por ejemplo, de un día a otro) puede saltarse el stop y perder algo más.";
    const problems = checkLimits(lv);
    $("lv-summary").innerHTML = problems.length
      ? '<span class="loss">Este nivel no cumple los límites: ' + esc(problems.join(", ")) + ".</span>"
      : esc(lv.summary);
    const pend = $("lv-pending");
    pend.hidden = lv.id === ag.current;
    pend.textContent = "Estás viendo «" + lv.name + "», pero el bot sigue en «" +
      (ag.levels.find((l) => l.id === ag.current) || {}).name + "». Desde la web no se cambia: el nivel se cambia en bot/config.toml y solo con tu aprobación.";
  }

  // ---------- 3. Gráfica ----------
  function renderChart() {
    const all = DATA.equity_curve;
    const pts = range ? all.slice(-range) : all;
    const labels = pts.map((p) => new Date(p.date + "T00:00:00").toLocaleDateString("es-ES", { day: "2-digit", month: "short" }));
    const init = DATA.account.initial_capital;
    $("legend-bench").textContent = DATA.meta.benchmark.name;
    const c = { accent: css("--accent"), bench: css("--bench"), muted: css("--muted"), line: css("--line"), fg: css("--fg"), surface: css("--surface-2") };

    const datasets = [
      { label: "Cartera del bot", data: pts.map((p) => p.portfolio), borderColor: c.accent, borderWidth: 2.2, pointRadius: pts.length < 15 ? 3 : 0, tension: 0.2,
        fill: { target: { value: init }, above: hexA(c.accent, 0.12), below: hexA(css("--loss"), 0.14) } },
      { label: DATA.meta.benchmark.name, data: pts.map((p) => p.benchmark), borderColor: c.bench, borderWidth: 1.6, borderDash: [5, 4], pointRadius: 0, tension: 0.2 },
      { label: "Capital inicial", data: pts.map(() => init), borderColor: c.muted, borderWidth: 1, borderDash: [2, 3], pointRadius: 0 }
    ];

    if (typeof Chart === "undefined") {
      $("equity-chart").parentElement.innerHTML = '<p class="muted small">No se pudo cargar la librería de gráficas (sin conexión a internet).</p>';
      return;
    }
    if (chart) { chart.data.labels = labels; chart.data.datasets = datasets; chart.update(); return; }

    chart = new Chart($("equity-chart"), {
      type: "line",
      data: { labels, datasets },
      options: {
        responsive: true, maintainAspectRatio: false, animation: { duration: 300 },
        interaction: { mode: "index", intersect: false },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: c.surface, borderColor: c.line, borderWidth: 1, titleColor: c.fg, bodyColor: c.fg, padding: 10,
            bodyFont: { family: "IBM Plex Mono" },
            callbacks: { label: (ctx) => " " + ctx.dataset.label + ": " + usd.format(ctx.parsed.y) + "  (" + pct((ctx.parsed.y / init - 1) * 100) + ")" }
          }
        },
        scales: {
          x: { grid: { display: false }, ticks: { color: c.muted, maxTicksLimit: 7, maxRotation: 0 }, border: { color: c.line } },
          y: { grid: { color: c.line }, border: { display: false }, ticks: { color: c.muted, callback: (v) => "$" + num(v, 0) } }
        }
      }
    });
  }
  function hexA(hex, a) {
    const h = hex.replace("#", "");
    const n = parseInt(h.length === 3 ? h.split("").map((x) => x + x).join("") : h, 16);
    return "rgba(" + (n >> 16 & 255) + "," + (n >> 8 & 255) + "," + (n & 255) + "," + a + ")";
  }
  document.querySelectorAll(".range button").forEach((b) => b.addEventListener("click", () => {
    document.querySelectorAll(".range button").forEach((x) => x.classList.toggle("active", x === b));
    range = Number(b.dataset.range);
    if (DATA) renderChart();
  }));

  // ---------- 4. Mejoras ----------
  function bar(label, value, min, unit) {
    const p = Math.min(100, (value / min) * 100);
    return '<div><div class="prog-label"><span>' + label + '</span><span class="num">' + value + " / " + min + " " + unit + "</span></div>" +
      '<div class="prog-bar"><span class="' + (p >= 100 ? "full" : "") + '" style="width:' + p + '%"></span></div></div>';
  }
  function renderLearning() {
    const L = DATA.learning;
    $("learn-rule").textContent = "Una observación pasa a regla con " + L.min_trades + " operaciones y " + L.min_weeks + " semanas como mínimo";
    $("count-obs").textContent = L.observing.length + L.learned.filter((r) => r.status === "back_to_observation").length;
    $("count-ok").textContent = L.learned.filter((r) => r.status === "active").length;

    const back = L.learned.filter((r) => r.status === "back_to_observation");
    $("panel-obs").innerHTML = L.observing.map((o) =>
      '<article class="item"><div class="item-head"><h3>' + esc(o.title) + '</h3><span class="tag">En observación</span></div>' +
      "<p>" + esc(o.detail) + "</p>" +
      '<div class="metric">' + esc(o.metric) + "</div>" +
      '<div class="progress">' + bar("Operaciones", o.trades, L.min_trades, "") + bar("Semanas", o.weeks, L.min_weeks, "") + "</div>" +
      (o.proposal ? '<div class="proposal">Cambio a probar cuando haya evidencia: <b>' + esc(o.proposal) + "</b> (necesita tu aprobación)</div>" : "") +
      "</article>").join("") +
      back.map((r) =>
      '<article class="item"><div class="item-head"><h3>' + esc(r.title) + '</h3><span class="tag tag-back">Volvió a observación</span></div>' +
      "<p>" + esc(r.detail) + "</p>" +
      '<div class="metric">' + esc(r.evidence.metric) + "</div></article>").join("") ||
      '<p class="muted small">Todavía no hay nada en observación. Hacen falta operaciones reales cerradas para detectar patrones.</p>';

    $("panel-ok").innerHTML = L.learned.filter((r) => r.status === "active").map((r) =>
      '<article class="item"><div class="item-head"><h3>' + esc(r.title) + "</h3>" +
      '<span class="tag ' + (r.kind === "evitar" ? "tag-avoid" : "tag-prio") + '">' + (r.kind === "evitar" ? "Evitar" : "Priorizar") + "</span></div>" +
      "<p>" + esc(r.detail) + "</p>" +
      '<div class="evidence"><span>Operaciones <b>' + r.evidence.trades + "</b></span><span>Semanas <b>" + r.evidence.weeks +
      "</b></span><span>Confirmada <b>" + fdate(r.confirmed_at) + "</b></span></div>" +
      '<div class="metric">' + esc(r.evidence.metric) + "</div></article>").join("") ||
      '<p class="muted small">Todavía no hay reglas confirmadas.</p>';
  }
  function selectTab(which) {
    const obs = which === "obs";
    $("tab-obs").setAttribute("aria-selected", String(obs));
    $("tab-ok").setAttribute("aria-selected", String(!obs));
    $("panel-obs").hidden = !obs;
    $("panel-ok").hidden = obs;
  }
  $("tab-obs").addEventListener("click", () => selectTab("obs"));
  $("tab-ok").addEventListener("click", () => selectTab("ok"));

  // ---------- 5. Desplegables ----------
  function renderPositions() {
    const P = DATA.positions;
    $("pos-count").textContent = P.length + " abiertas · invertido " + usd.format(DATA.account.invested);
    $("pos-table").innerHTML = "<thead><tr><th>Activo</th><th>Abierta</th><th class=r>Entrada</th><th class=r>Actual</th><th class=r>Stop</th><th class=r>Valor</th><th class=r>P&amp;L</th><th>Motivo de entrada</th></tr></thead><tbody>" +
      P.map((p) => "<tr><td><b>" + esc(p.symbol) + '</b><span class="mkt">' + esc(p.market) + "</span></td><td>" + fdate(p.opened_at, true) +
        '</td><td class="r num">' + price(p.entry_price) + '</td><td class="r num">' + price(p.current_price) +
        '</td><td class="r num loss">' + price(p.stop_loss) + '</td><td class="r num">' + usd.format(p.value) +
        '</td><td class="r num ' + cls(p.unrealized_pnl) + '">' + money(p.unrealized_pnl) +
        '</td><td class="reason">' + esc(p.entry_reason) + "</td></tr>").join("") +
      (P.length ? "" : '<tr><td colspan="8" class="muted">Ahora mismo no hay posiciones abiertas: todo está en liquidez.</td></tr>') + "</tbody>";
  }
  function renderTrades() {
    const T = DATA.trades;
    const total = T.reduce((s, t) => s + t.pnl, 0);
    $("trades-count").innerHTML = T.length + ' cerradas · <span class="' + cls(total) + '">' + money(total) + "</span>";
    $("trades-table").innerHTML = "<thead><tr><th>Activo</th><th>Entrada</th><th>Salida</th><th class=r>Precio entrada</th><th class=r>Precio salida</th><th class=r>Comisiones</th><th class=r>Resultado</th><th>Motivo</th></tr></thead><tbody>" +
      T.map((t) => "<tr><td><b>" + esc(t.symbol) + '</b><span class="mkt">' + esc(t.market) + "</span></td><td>" + fdate(t.opened_at, true) +
        "</td><td>" + fdate(t.closed_at, true) + '</td><td class="r num">' + price(t.entry_price) + '</td><td class="r num">' + price(t.exit_price) +
        '</td><td class="r num muted">' + usd.format(t.fees) + '</td><td class="r num ' + cls(t.pnl) + '">' + money(t.pnl) + "<br><span class=small>" + pct(t.pnl_pct) + "</span>" +
        '</td><td class="reason"><b>Entra:</b> ' + esc(t.entry_reason) + "<br><b>Sale:</b> " + esc(t.exit_reason) + "</td></tr>").join("") +
      (T.length ? "" : '<tr><td colspan="8" class="muted">Todavía no se ha cerrado ninguna operación.</td></tr>') + "</tbody>";
  }
  function renderLogs() {
    const lg = DATA.logs;
    const errs = lg.filter((l) => l.level === "error").length, warns = lg.filter((l) => l.level === "warning").length;
    $("logs-count").textContent = lg.length + " entradas · " + errs + " errores · " + warns + " avisos";
    $("logs").innerHTML = lg.map((l) => "<li><time>" + fdate(l.ts, true) + '</time><span class="lv lv-' + esc(l.level) + '">' + esc(l.level) + "</span><span>" + esc(l.message) + "</span></li>").join("");
  }
  function renderLimits() {
    const r = DATA.risk_limits;
    $("limits").innerHTML = [
      "Máximo " + r.max_per_asset_pct + " % del capital en un mismo activo.",
      "Mínimo " + r.min_cash_pct + " % siempre en liquidez.",
      "Stop-loss obligatorio en cada compra.",
      "Sin apalancamiento y sin ventas en corto.",
      "Freno de emergencia: si la cartera cae un " + r.emergency_brake_drawdown_pct + " % desde su máximo, el bot deja de abrir operaciones y avisa. Caída actual desde el máximo: " + pct(DATA.account.drawdown_from_peak_pct) + ".",
      "Costes simulados por operación: comisión " + num(r.fee_pct_per_side, 2) + " % y deslizamiento " + num(r.slippage_pct_per_side, 2) + " % en cada lado."
    ].map((x) => "<li>" + esc(x) + "</li>").join("");
  }

  load();
  if (CFG.refreshSeconds > 0) setInterval(load, CFG.refreshSeconds * 1000);
})();
