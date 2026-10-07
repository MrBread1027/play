"use strict";

const $ = (s) => document.querySelector(s);
let DATA = null;
let tab = "results";
let LIVE = null;
try { tab = localStorage.getItem("tab") || tab; } catch (e) {}

const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

function pct(p) {
  const s = p >= 0.001 ? (p * 100).toFixed(2) : (p * 100).toFixed(6).replace(/0+$/, "");
  return `${s}% <span class="sub">(1/${Math.round(1 / p).toLocaleString()})</span>`;
}

function perms(n) {
  const c = {};
  for (const d of n) c[d] = (c[d] || 0) + 1;
  let r = 24;
  for (const k in c) r /= [1, 1, 2, 6, 24][c[k]];
  return r;
}

function odds4d(n) {
  const k = perms(n);
  return { first: 1 / 10000, any: 23 / 10000, ibox_any: Math.min(1, (23 * k) / 10000), perms: k };
}

// ------------------------------------------------------------ 4D 公司
function renderCompany(c) {
  const v = c.v2;
  if (!v) return `<section class="card err">资料不足，至少需要 150 期才能计算 V2。</section>`;
  const L = v.labels;
  const maxPart = Math.max(...v.picks.flatMap((p) => Object.values(p.parts).map(Math.abs)), 0.01);

  const picks = v.picks.map((p, i) => {
    const o = odds4d(p.num);
    const bars = Object.entries(p.parts).map(([k, x]) => `
      <div class="bar"><span>${esc(L[k])}</span>
        <i><b class="${x < 0 ? "neg" : ""}" style="width:${(Math.abs(x) / maxPart) * 100}%"></b></i>
        <em>${x > 0 ? "+" : ""}${x.toFixed(2)}</em></div>`).join("");
    return `
    <div class="pick v2">
      <div class="num">${esc(p.num)}</div>
      <div>
        <div class="score"><span class="rank">#${i + 1}</span> 评分 <b>${p.score.toFixed(1)}</b>
          <span class="sub">（平均号码 = 50）</span></div>
        <div class="odds">十年出现 ${p.count} 次 · 近半年 ${p.recent} 次 · 模式 ${esc(p.pattern)}</div>
        <div class="odds">任何奖 <b>${pct(o.any)}</b> · iBox(${o.perms}组) <b>${pct(o.ibox_any)}</b></div>
      </div>
      <details><summary>评分组成</summary>${bars}</details>
    </div>`;
  }).join("");

  const bt = v.backtest;
  const rows = bt.rows.map((r) => `
    <tr><td>Top ${r.k}</td>
      <td>${r.hits} <span class="sub">/ ${r.expected}</span></td>
      <td>${(r.rate * 100).toFixed(2)}%</td>
      <td>${r.first} <span class="sub">/ ${r.first_expected}</span></td>
      <td class="${r.p_value < 0.05 ? "sig" : ""}">${r.p_value.toFixed(2)}</td></tr>`).join("");
  const cal = bt.calibrated;
  const anySig = bt.rows.some((r) => r.p_value < 0.05);
  const w = v.weights;
  const last = c.last_result ? c.last_result.top3.map((n) => `<span class="ball lg">${esc(n)}</span>`).join("") : "";

  return `
  <section class="card hero">
    <h2>${esc(c.name)} · V2 推荐</h2>
    <p class="sub">综合评分引擎，分析 ${c.draws} 期（${esc(c.first_draw)} 至 ${esc(c.last_draw)}），
      已过滤 ${(10000 - v.filters.kept).toLocaleString()} 个极端组合</p>
    ${picks}
  </section>

  <section class="card">
    <h2>Walk-forward 回测</h2>
    <p class="sub">从 ${esc(bt.test_from)} 起共 ${bt.draws} 期：每期只用当时之前的资料打分，再对照当期结果。
      斜线后是纯随机的期望值。</p>
    <table class="bt-table">
      <thead><tr><th></th><th>中奖数</th><th>命中率</th><th>头奖</th><th>p 值</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
    <div class="bt">
      <b>校准后的真实概率：</b>推荐前 4 个号码中任何奖的实际命中率
      ${(cal.rate * 100).toFixed(2)}%（95% 区间 ${(cal.lo * 100).toFixed(2)}%–${(cal.hi * 100).toFixed(2)}%），
      随机为 ${(cal.random * 100).toFixed(2)}%。<br>
      ${anySig ? "有一项 p 值低于 0.05，但同时检验多项时偶尔出现属于正常，需要更多期数确认。"
               : "所有 p 值都高于 0.05：模型没有显著优于随机选号。"}
    </div>
  </section>

  <section class="card">
    <h2>模型设定</h2>
    <div class="kv">${Object.keys(w).map((k) => `<span>${esc(L[k])}</span><span>${Math.round(w[k] * 100)}%</span>`).join("")}</div>
    <p class="sub" style="margin-top:10px">机器学习学到的特征权重：
      ${Object.entries(v.ml_weights).map(([k, x]) => `${esc(L[k])} ${x > 0 ? "+" : ""}${x}`).join(" · ")}</p>
    <p class="sub">过滤规则：数字和在 ${v.filters.sum_lo}–${v.filters.sum_hi} 以外、AAAA、全奇/全偶且全大/全小。</p>
  </section>

  <section class="card">
    <h2>上期头三奖</h2>
    <p class="sub">${esc(c.last_draw)}</p>
    <div class="balls">${last}</div>
  </section>`;
}

// ------------------------------------------------------------ Jackpot
function renderJackpot() {
  const lotto = Object.values(DATA.lotto).map((t) => `
    <section class="card">
      <h2>${esc(t.name)}</h2>
      <p class="sub">根据 ${t.draws} 期 · 上期 ${esc((t.last_result || []).join(" "))}</p>
      <div class="kv"><span>热号推荐</span><span></span></div>
      <div class="balls">${t.hot_pick.map((b) => `<span class="ball">${b}</span>`).join("")}</div>
      <div class="kv"><span>冷热混合（4 热 + 2 最久没开）</span><span></span></div>
      <div class="balls">${t.mix_pick.map((b) => `<span class="ball">${b}</span>`).join("")}</div>
      <div class="kv"><span>头奖概率（每组）</span><span>${pct(t.p)}</span></div>
      <div class="bt">回测 ${t.backtest.draws} 期：热号平均每期中 <b>${t.backtest.avg_match.toFixed(2)}</b> 个，
        随机选号平均中 <b>${t.backtest.random_match.toFixed(2)}</b> 个。</div>
    </section>`).join("");

  const jp4d = Object.values(DATA.companies).map((c) => `
    <section class="card">
      <h2>${esc(c.jackpot.name)}</h2>
      <p class="sub">两个号码同时开在头三奖中的任意两个</p>
      <div class="balls">${c.jackpot.pair.map((n) => `<span class="ball lg">${esc(n)}</span>`).join('<span style="align-self:center">+</span>')}</div>
      <div class="kv"><span>Jackpot 1 概率</span><span>${pct(c.jackpot.p)}</span></div>
    </section>`).join("");
  return lotto + jp4d;
}

// ------------------------------------------------------------ 查号码
function renderCheck() {
  $("#view").innerHTML = "";
  $("#view").appendChild($("#check-tpl").content.cloneNode(true));
  const input = $("#num");
  input.addEventListener("input", () => {
    input.value = input.value.replace(/\D/g, "").slice(0, 4);
    const n = input.value;
    if (n.length < 4) { $("#check-out").innerHTML = ""; return; }
    const o = odds4d(n);
    const found = Object.values(DATA ? DATA.companies : {})
      .filter((c) => c.v2 && c.v2.picks.some((p) => p.num === n)).map((c) => c.name);
    $("#check-out").innerHTML = `
      <div class="kv">
        <span>头奖 (Big)</span><span>${pct(o.first)}</span>
        <span>任何奖 (Big)</span><span>${pct(o.any)}</span>
        <span>iBox 组合数</span><span>${o.perms}</span>
        <span>iBox 任何奖</span><span>${pct(o.ibox_any)}</span>
      </div>
      <div class="bt">每个 4 位号码的概率都一样。${found.length ? `这个号码在 ${esc(found.join("、"))} 的推荐名单里。` : ""}</div>`;
  });
  input.focus();
}

// ------------------------------------------------------------ 最新成绩
function prizeOf(num, d) {
  const names = ["头奖", "二奖", "三奖"];
  const i = (d.top3 || []).indexOf(num);
  if (i >= 0) return names[i];
  if ((d.special || []).includes(num)) return "特别奖";
  if ((d.consolation || []).includes(num)) return "安慰奖";
  const key = [...num].sort().join("");
  const all = [...(d.top3 || []), ...(d.special || []), ...(d.consolation || [])];
  const box = all.find((n) => [...n].sort().join("") === key);
  return box ? `iBox 中（${box}）` : null;
}

function renderResults() {
  const live = (LIVE && LIVE.companies) || {};
  const cards = Object.entries(DATA.companies).map(([key, c]) => {
    const v2 = c.v2 || {};
    const lv = live[key];
    let res, picks;
    if (lv && lv.date > (c.last_draw || "")) {          // 新的一期（可能还在开奖中）
      res = lv;
      picks = (v2.picks || []).map((p) => p.num);
    } else {
      res = c.last_result || {};
      picks = (v2.last_check && v2.last_check.picks) || [];
    }
    const date = res.date || c.last_draw;
    const drawNo = lv && lv.date === date ? ` · 第 ${esc(lv.draw_no)} 期` : "";
    const liveNow = lv && lv.live && res === lv;
    const mine = new Set(picks);
    const grid = (arr) => `<div class="grid5">${(arr || []).map((n) =>
      `<span class="${mine.has(n) ? "hit" : ""}">${esc(n)}</span>`).join("")}</div>`;
    const top = ["头奖", "二奖", "三奖"].map((name, i) => `
      <div class="prize"><small>${name}</small><b class="${mine.has((res.top3 || [])[i]) ? "hit" : ""}">${esc((res.top3 || [])[i] || "····")}</b></div>`).join("");
    const check = picks.map((n) => {
      const p = prizeOf(n, res);
      return `<div class="check ${p ? "won" : ""}"><span>${esc(n)}</span><em>${p ? esc(p) : liveNow ? "等待中" : "没中"}</em></div>`;
    }).join("");
    return `
    <section class="card result">
      <div class="r-head"><h2>${esc(c.name)}</h2>
        ${liveNow ? `<span class="live-dot">开奖中</span>` : ""}</div>
      <p class="sub">${esc(date)}${drawNo}</p>
      <div class="prizes">${top}</div>
      <p class="label">特别奖</p>${grid(res.special)}
      <p class="label">安慰奖</p>${grid(res.consolation)}
      <p class="label gold">开奖前 V2 推荐对奖</p>
      ${check || `<p class="sub">（等下一期开奖后显示）</p>`}
    </section>`;
  }).join("");

  const lotto = Object.values(DATA.lotto).map((t) => `
    <div class="kv"><span>${esc(t.name)} <small class="sub">${esc(t.last_draw || "")}</small></span><span></span></div>
    <div class="balls">${(t.last_result || []).map((b) => `<span class="ball">${b}</span>`).join("")}</div>`).join("");

  const checked = LIVE && LIVE.checked ? `成绩检查于 ${esc(LIVE.checked.replace("T", " "))}` : "";
  $("#view").innerHTML = `
    <p class="sub center">${checked} · 开奖时间（晚上 7-9 点）约每 10 分钟更新</p>
    ${cards}
    <section class="card"><h2>Sports Toto Jackpot</h2>${lotto}</section>`;
}

// ------------------------------------------------------------ 主流程
function render() {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  if (tab === "check") return renderCheck();
  if (!DATA) { $("#view").innerHTML = `<section class="card err">还没有资料。请先在电脑执行 <code>python app.py update</code>。</section>`; return; }
  if (tab === "calc") return renderCalc();
  if (tab === "results") return renderResults();
  $("#view").innerHTML = tab === "jackpot" ? renderJackpot() : renderCompany(DATA.companies[tab]);
}

// ------------------------------------------------------------ 计算
let calcState = { comp: "magnum", method: "hot" };
try { Object.assign(calcState, JSON.parse(localStorage.getItem("calc") || "{}")); } catch (e) {}

function renderCalc() {
  const comps = Object.entries(DATA.companies);
  const methods = DATA.methods || [];
  const opt = (v, label, sel) => `<option value="${esc(v)}"${v === sel ? " selected" : ""}>${esc(label)}</option>`;
  $("#view").innerHTML = `
    <section class="card">
      <h2>选号计算</h2>
      <label class="field">公司
        <select id="c-comp">${comps.map(([k, c]) => opt(k, c.name, calcState.comp)).join("")}</select></label>
      <label class="field">计算方式
        <select id="c-method">${methods.map((m) => opt(m.id, m.name, calcState.method)).join("")}</select></label>
      <p class="sub" id="c-desc"></p>
      <button id="c-go" class="go">计算</button>
    </section>
    <div id="c-out"></div>`;

  const desc = () => {
    const m = methods.find((x) => x.id === $("#c-method").value);
    $("#c-desc").textContent = m ? m.desc : "";
  };
  $("#c-method").addEventListener("change", desc);
  desc();

  $("#c-go").addEventListener("click", () => {
    calcState = { comp: $("#c-comp").value, method: $("#c-method").value };
    try { localStorage.setItem("calc", JSON.stringify(calcState)); } catch (e) {}
    const c = DATA.companies[calcState.comp];
    const m = methods.find((x) => x.id === calcState.method);
    const picks = (c.methods || {})[calcState.method] || [];
    $("#c-out").innerHTML = `
      <section class="card">
        <h2>${esc(c.name)} · ${esc(m.name)}</h2>
        <p class="sub">根据 ${c.draws} 期资料，最新到 ${esc(c.last_draw)}</p>
        ${picks.map((p, i) => {
          const o = odds4d(p.num);
          return `<div class="pick">
            <div class="num">${esc(p.num)}</div>
            <div class="stats"><span class="rank">#${i + 1}</span> ${esc(p.why)}</div>
            <div class="odds">头奖 <b>${pct(o.first)}</b> · 任何奖 <b>${pct(o.any)}</b><br>
              iBox(${o.perms}组) 任何奖 <b>${pct(o.ibox_any)}</b></div>
          </div>`;
        }).join("")}
      </section>`;
    $("#c-out").scrollIntoView({ behavior: "smooth", block: "start" });
  });
}

async function getJSON(name) {
  const r = await fetch(name + "?t=" + Date.now(), { cache: "no-store" });
  if (!r.ok) throw new Error(r.status);
  return r.json();
}

async function load(quiet) {
  if (!quiet) $("#refresh").classList.add("spin");
  const before = JSON.stringify([DATA && DATA.updated, LIVE && LIVE.companies]);
  try {
    DATA = await getJSON("data.json");
    $("#updated").textContent = "资料更新: " + DATA.updated.replace("T", " ");
  } catch (e) {
    $("#updated").textContent = DATA ? "离线中，显示上次资料" : "无法载入资料";
  }
  try { LIVE = await getJSON("live.json"); } catch (e) {}
  $("#refresh").classList.remove("spin");
  const changed = before !== JSON.stringify([DATA && DATA.updated, LIVE && LIVE.companies]);
  // 自动刷新时只在成绩页重画，避免打断其他页面的操作
  if (!quiet || (changed && tab === "results")) render();
}

// 打开 App 时每分钟检查一次新成绩
setInterval(() => { if (document.visibilityState === "visible") load(true); }, 60000);
document.addEventListener("visibilitychange", () => { if (document.visibilityState === "visible") load(true); });

$("#tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  tab = b.dataset.tab;
  try { localStorage.setItem("tab", tab); } catch (e) {}
  render();
  window.scrollTo(0, 0);
});
$("#refresh").addEventListener("click", () => load());

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
load();
