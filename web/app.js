"use strict";

const $ = (s) => document.querySelector(s);
let DATA = null;
let tab = "magnum";
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
  const bt = c.backtest;
  const picks = c.picks.map((p, i) => `
    <div class="pick">
      <div class="num">${esc(p.num)}</div>
      <div class="stats"><span class="rank">#${i + 1}</span>
        三年出现 <b>${p.count}</b> 次 · 近半年 ${p.recent} 次 · 最后 ${esc(p.last_seen)}</div>
      <div class="odds">头奖 <b>${pct(p.odds.first)}</b> · 任何奖 <b>${pct(p.odds.any)}</b><br>
        iBox(${p.odds.perms}组) 任何奖 <b>${pct(p.odds.ibox_any)}</b></div>
    </div>`).join("");

  const last = c.last_result ? c.last_result.top3.map((n) => `<span class="ball lg">${esc(n)}</span>`).join("") : "";

  return `
  <section class="card">
    <h2>${esc(c.name)} 推荐号码</h2>
    <p class="sub">根据 ${c.draws} 期资料（${esc(c.first_draw)} 至 ${esc(c.last_draw)}），按三年出现次数 + 近半年加权排名</p>
    ${picks}
  </section>
  <section class="card">
    <h2>位数频率组合</h2>
    <p class="sub">千、百、十、个位各自最常出现的数字</p>
    <div class="balls"><span class="ball lg">${esc(c.digit_pick.num)}</span></div>
    <div class="odds">任何奖 <b>${pct(c.digit_pick.odds.any)}</b></div>
  </section>
  <section class="card">
    <h2>上期头三奖</h2>
    <p class="sub">${esc(c.last_draw)}</p>
    <div class="balls">${last}</div>
  </section>
  <section class="card">
    <h2>历史回测：推荐号码真的比较准吗？</h2>
    <div class="bt">最近 ${bt.draws} 期，每期用当时的资料选出前 ${bt.picks_per_draw} 个推荐号：<br>
      推荐号命中率 <b>${(bt.hit_rate * 100).toFixed(2)}%</b>，随便买的命中率是 <b>${(bt.random_rate * 100).toFixed(2)}%</b>。<br>
      两者接近，说明历史频率没有预测能力。</div>
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
      .filter((c) => c.picks.some((p) => p.num === n)).map((c) => c.name);
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

// ------------------------------------------------------------ 主流程
function render() {
  document.querySelectorAll("#tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  if (tab === "check") return renderCheck();
  if (!DATA) { $("#view").innerHTML = `<section class="card err">还没有资料。请先在电脑执行 <code>python app.py update</code>。</section>`; return; }
  if (tab === "calc") return renderCalc();
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

async function load() {
  $("#refresh").classList.add("spin");
  try {
    const r = await fetch("data.json?t=" + Date.now(), { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    DATA = await r.json();
    $("#updated").textContent = "资料更新: " + DATA.updated.replace("T", " ");
  } catch (e) {
    $("#updated").textContent = DATA ? "离线中，显示上次资料" : "无法载入资料";
  }
  $("#refresh").classList.remove("spin");
  render();
}

$("#tabs").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  tab = b.dataset.tab;
  try { localStorage.setItem("tab", tab); } catch (e) {}
  render();
  window.scrollTo(0, 0);
});
$("#refresh").addEventListener("click", load);

if ("serviceWorker" in navigator) navigator.serviceWorker.register("sw.js").catch(() => {});
load();
