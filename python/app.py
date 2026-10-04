"""马来西亚 4D / Jackpot 号码分析器 - Python 版

用法:
  python app.py            打开电脑版界面
  python app.py update     更新资料，有新开奖才重新计算（无界面，给自动排程用）
  python app.py update --force   不管有没有新开奖都重新计算
  python app.py serve      在本机开网页版 (手机同一 WiFi 可访问)
"""
import json
import os
import socket
import sys
import threading
from datetime import datetime
from pathlib import Path

from lotto import analyze, fetch

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "draws.json"
OUT_PATH = ROOT / "web" / "data.json"
LIVE_PATH = ROOT / "web" / "live.json"

DISCLAIMER = ("提醒：每期开奖都是独立随机的。推荐号码只是过去三年出现较多的号码，"
              "真实中奖概率由游戏规则决定，不会因为历史资料而提高。请理性投注。")


def load_db():
    return json.loads(DB_PATH.read_text("utf-8")) if DB_PATH.exists() else {}


def save(db, result):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, separators=(",", ":")), "utf-8")
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), "utf-8")


def run_update(progress=None, force=False):
    """有新开奖才重新计算（V2 引擎约需 1 分钟）。没有新资料时 result 为 None。"""
    db = load_db()
    added = fetch.update(db, progress=progress)
    if not added and not force and OUT_PATH.exists():
        return 0, None
    result = analyze.build(db)
    save(db, result)
    return added, result


def save_live():
    """抓最新一期（含开奖中）的成绩存成 live.json，内容有变化时返回 True。"""
    try:
        live = fetch.fetch_live()
    except Exception:
        return False, None
    old = json.loads(LIVE_PATH.read_text("utf-8")) if LIVE_PATH.exists() else {}
    changed = old.get("companies") != live
    out = {"checked": datetime.now().isoformat(timespec="minutes"), "companies": live}
    LIVE_PATH.write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), "utf-8")
    return changed, out


def load_result():
    if OUT_PATH.exists():
        return json.loads(OUT_PATH.read_text("utf-8"))
    db = load_db()
    return analyze.build(db) if db else None


def pct(p):
    if p >= 0.001:
        s = f"{p * 100:.2f}%"
    else:
        s = f"{p * 100:.6f}%".rstrip("0")
    return f"{s} (1/{round(1 / p):,})"


# ================================================================ CLI
def cli_update():
    def prog(i, n, c, d):
        if i % 50 == 0 or i == n:
            print(f"  {i}/{n}", flush=True)
    print("正在更新资料 ...")
    live_changed, _ = save_live()
    added, r = run_update(prog, force="--force" in sys.argv)
    print(f"新增 {added} 期。实时成绩{'有' if live_changed else '没有'}变化。")
    if os.environ.get("GITHUB_OUTPUT"):   # 告诉 GitHub Actions 要不要发布
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write("changed=true\n" if r or live_changed else "changed=false\n")
    if not r:
        print("没有新开奖，不用重新计算。")
        return
    for c in r["companies"].values():
        if c.get("v2"):
            print(f"{c['name']:<16} {c['draws']} 期, V2 推荐: {' '.join(p['num'] for p in c['v2']['picks'])}")
    for t in r["lotto"].values():
        print(f"{t['name']:<16} {t['draws']} 期, 推荐: {t['hot_pick']}")


def cli_serve(port=8000):
    import functools
    import http.server
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT / "web"))
    try:
        # 不会真的发送资料，只是让系统选出连到局域网的那张网卡
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.168.0.1", 80))
            ip = s.getsockname()[0]
    except OSError:
        ip = socket.gethostbyname(socket.gethostname())
    print("=" * 50)
    print(f"  iPhone 用 Safari 打开:  http://{ip}:{port}")
    print(f"  电脑打开:              http://localhost:{port}")
    print("  (iPhone 和电脑要连同一个 WiFi，这个窗口不要关)")
    print("=" * 50)
    http.server.ThreadingHTTPServer(("0.0.0.0", port), handler).serve_forever()


# ================================================================ GUI
def gui():
    import tkinter as tk
    from tkinter import messagebox, ttk

    BG, CARD, LINE = "#1a0b2e", "#2a1449", "#4a2d78"
    GOLD, GOLD2, INK, MUTED, DARK = "#d4af37", "#f3d77a", "#f5ecd7", "#b9a8d4", "#2a1449"
    FONT = "Microsoft YaHei UI"

    root = tk.Tk()
    root.title("4D 号码分析器 V2 - Magnum / Da Ma Cai / Toto")
    root.geometry("1040x700")
    root.configure(bg=BG)
    for k, v in (("background", CARD), ("foreground", INK),
                 ("selectBackground", GOLD), ("selectForeground", DARK)):
        root.option_add(f"*TCombobox*Listbox.{k}", v)

    style = ttk.Style()
    style.theme_use("clam")
    style.configure(".", background=BG, foreground=INK, fieldbackground=CARD,
                    bordercolor=LINE, lightcolor=LINE, darkcolor=LINE, font=(FONT, 10))
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Muted.TLabel", foreground=MUTED)
    style.configure("Big.TLabel", font=(FONT, 13, "bold"), foreground=GOLD2)
    style.configure("Title.TLabel", font=(FONT, 16, "bold"), foreground=GOLD2)
    style.configure("TNotebook", background=BG, bordercolor=LINE, tabmargins=(6, 6, 6, 0))
    style.configure("TNotebook.Tab", background=CARD, foreground=INK, padding=(14, 6), bordercolor=LINE)
    style.map("TNotebook.Tab", background=[("selected", GOLD)], foreground=[("selected", DARK)])
    style.configure("TButton", background=GOLD, foreground=DARK, bordercolor=GOLD,
                    font=(FONT, 10, "bold"), padding=(14, 5))
    style.map("TButton", background=[("active", GOLD2), ("disabled", LINE)])
    style.configure("Treeview", background=CARD, fieldbackground=CARD, foreground=INK,
                    rowheight=28, font=(FONT, 10), bordercolor=LINE)
    style.map("Treeview", background=[("selected", GOLD)], foreground=[("selected", DARK)])
    style.configure("Treeview.Heading", background="#3b1670", foreground=GOLD2,
                    font=(FONT, 10, "bold"), bordercolor=LINE)
    style.map("Treeview.Heading", background=[("active", "#4b1d8a")])
    style.configure("TCombobox", fieldbackground=CARD, foreground=INK, background=GOLD, arrowcolor=DARK)
    style.map("TCombobox", fieldbackground=[("readonly", CARD)], foreground=[("readonly", INK)])
    style.configure("Horizontal.TProgressbar", troughcolor=CARD, background=GOLD, bordercolor=LINE)
    style.configure("TLabelframe", background=BG, bordercolor=GOLD)
    style.configure("TLabelframe.Label", background=BG, foreground=GOLD2, font=(FONT, 11, "bold"))
    style.configure("TCheckbutton", background=BG, foreground=INK, indicatorbackground=CARD,
                    indicatorforeground=GOLD2)
    style.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", GOLD)])

    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="4D 号码分析 V2", style="Title.TLabel").pack(side="left", padx=(0, 16))
    btn = ttk.Button(top, text="更新资料")
    btn.pack(side="left")
    auto = tk.BooleanVar(value=True)
    ttk.Checkbutton(top, text="开奖时间自动更新（每晚 7-9 点，每分钟看实时成绩）",
                    variable=auto).pack(side="left", padx=(12, 0))
    status = ttk.Label(top, text="")
    status.pack(side="left", padx=12)
    bar = ttk.Progressbar(top, length=220)
    bar.pack(side="right")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8)
    ttk.Label(root, text=DISCLAIMER, foreground="#f0b47a", wraplength=1000,
              padding=8).pack(fill="x")

    state = {"r": None, "live": None}

    def render(r):
        state["r"] = r
        for t in nb.tabs():
            nb.forget(t)
        if not r:
            status.config(text="还没有资料，请按「更新资料」（第一次约需 5-10 分钟）")
            return
        status.config(text=f"最后更新: {r['updated'].replace('T', ' ')}")
        render_results(r)
        render_calc(r)
        for c in r["companies"].values():
            f = ttk.Frame(nb, padding=12)
            nb.add(f, text=c["name"])
            v = c.get("v2")
            ttk.Label(f, text=f"{c['name']} · V2 综合评分推荐", style="Big.TLabel").pack(anchor="w")
            if not v:
                ttk.Label(f, text="资料不足，至少需要 150 期。").pack(anchor="w")
                continue
            ttk.Label(f, text=f"分析 {c['draws']} 期（{c['first_draw']} 至 {c['last_draw']}），"
                              f"已过滤 {10000 - v['filters']['kept']} 个极端组合。评分：平均号码 = 50",
                      style="Muted.TLabel").pack(anchor="w")
            L = v["labels"]
            cols = ("num", "score", "count", "recent", "pat", "any", "ibox", "parts")
            heads = ("推荐号码", "评分", "三年出现", "近半年", "模式", "任何奖概率", "iBox 任何奖",
                     "评分组成（最大的三项）")
            widths = (80, 60, 70, 60, 60, 130, 150, 330)
            tv = ttk.Treeview(f, columns=cols, show="headings", height=len(v["picks"]))
            for col, h, w in zip(cols, heads, widths):
                tv.heading(col, text=h)
                tv.column(col, width=w, anchor="w" if col == "parts" else "center")
            for p in v["picks"]:
                o = analyze.odds_4d(p["num"])
                top3 = sorted(p["parts"].items(), key=lambda kv: -abs(kv[1]))[:3]
                tv.insert("", "end", values=(
                    p["num"], f"{p['score']:.1f}", p["count"], p["recent"], p["pattern"],
                    pct(o["any"]), f"{pct(o['ibox_any'])} ×{o['perms']}",
                    "  ".join(f"{L[k]} {x:+.2f}" for k, x in top3)))
            tv.pack(fill="x", pady=(8, 12))

            bt = v["backtest"]
            ttk.Label(f, text=f"Walk-forward 回测：从 {bt['test_from']} 起 {bt['draws']} 期，"
                              f"每期只用当时之前的资料", style="Big.TLabel").pack(anchor="w")
            cols = ("k", "hits", "exp", "rate", "first", "p")
            heads = ("推荐数", "中奖数", "随机期望", "命中率", "头奖（随机期望）", "p 值")
            bv = ttk.Treeview(f, columns=cols, show="headings", height=len(bt["rows"]))
            for col, h in zip(cols, heads):
                bv.heading(col, text=h)
                bv.column(col, width=120, anchor="center")
            for row in bt["rows"]:
                bv.insert("", "end", values=(f"Top {row['k']}", row["hits"], row["expected"],
                                             f"{row['rate'] * 100:.2f}%",
                                             f"{row['first']} ({row['first_expected']})",
                                             f"{row['p_value']:.2f}"))
            bv.pack(anchor="w", pady=(6, 10))

            cal = bt["calibrated"]
            sig = any(row["p_value"] < .05 for row in bt["rows"])
            jp = c["jackpot"]
            info = (f"校准后的真实概率：推荐号码中任何奖 {cal['rate'] * 100:.2f}%"
                    f"（95% 区间 {cal['lo'] * 100:.2f}%–{cal['hi'] * 100:.2f}%），随机 {cal['random'] * 100:.2f}%。"
                    + ("有 p 值低于 0.05，但同时检验多项时偶尔出现属正常。" if sig
                       else "所有 p 值都高于 0.05：模型没有显著优于随机选号。")
                    + f"\n{jp['name']} 推荐组合: {' + '.join(jp['pair'])}    Jackpot 1 概率 约 1/{jp['one_in']:,}"
                    + "\n机器学习权重: " + " · ".join(f"{L[k]} {w:+.3f}" for k, w in v["ml_weights"].items()))
            ttk.Label(f, text=info, justify="left", wraplength=980).pack(anchor="w")

        f = ttk.Frame(nb, padding=10)
        nb.add(f, text="Toto Jackpot 6/50·55·58")
        for t in r["lotto"].values():
            bt = t["backtest"]
            box = ttk.LabelFrame(f, text=f"{t['name']}  ·  分析 {t['draws']} 期", padding=8)
            box.pack(fill="x", pady=6)
            ttk.Label(box, text="热号推荐:  " + "  ".join(f"{b:02d}" for b in t["hot_pick"]),
                      style="Big.TLabel").pack(anchor="w")
            ttk.Label(box, text="冷热混合:  " + "  ".join(f"{b:02d}" for b in t["mix_pick"])).pack(anchor="w")
            ttk.Label(box, text=f"头奖概率: {pct(t['p'])}    上期: {t['last_result']}\n"
                                f"回测: 热号平均每期中 {bt['avg_match']:.2f} 个，"
                                f"纯随机应为 {bt['random_match']:.2f} 个").pack(anchor="w")

    def render_results(r):
        f = tk.Frame(nb, bg=BG, padx=10, pady=10)
        nb.add(f, text="最新成绩")
        companies = (state["live"] or {}).get("companies", {})
        for col, (key, c) in enumerate(r["companies"].items()):
            f.grid_columnconfigure(col, weight=1, uniform="c")
            box = tk.Frame(f, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=10, pady=8)
            box.grid(row=0, column=col, sticky="nsew", padx=5)
            v2 = c.get("v2") or {}
            lv = companies.get(key)
            if lv and lv["date"] > (c["last_draw"] or ""):
                # 新的一期（可能还在开奖中）：拿开奖前的 V2 推荐来对奖
                res = lv
                picks = [p["num"] for p in v2.get("picks", [])]
                lc = {"picks": picks, "result": [{"num": n, **analyze.prize_of(n, lv)} for n in picks]}
            else:
                res = c.get("last_result") or {}
                lc = v2.get("last_check") or {}
            mine = set(lc.get("picks", []))
            draw_no = f" 第 {lv['draw_no']} 期" if lv and lv["date"] == (res.get("date") or c["last_draw"]) else ""
            live_now = bool(lv and lv["live"] and res is lv)
            tk.Label(box, text=c["name"], bg=CARD, fg=GOLD2, font=(FONT, 12, "bold")).pack(anchor="w")
            tk.Label(box, text=f"{res.get('date') or c['last_draw']}{draw_no}" + ("   ● 开奖中" if live_now else ""),
                     bg=CARD, fg="#ff8a8a" if live_now else MUTED, font=(FONT, 9)).pack(anchor="w")

            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", pady=(6, 4))
            for i, (name, n) in enumerate(zip(("头奖", "二奖", "三奖"), res.get("top3", []))):
                cell = tk.Frame(row, bg=CARD)
                cell.grid(row=0, column=i, padx=3, sticky="ew")
                row.grid_columnconfigure(i, weight=1)
                tk.Label(cell, text=name, bg=CARD, fg=MUTED, font=(FONT, 9)).pack()
                tk.Label(cell, text=n, bg=GOLD, fg=DARK, font=("Consolas", 17, "bold"),
                         padx=6, pady=2).pack(fill="x")

            for title, key in (("特别奖", "special"), ("安慰奖", "consolation")):
                tk.Label(box, text=title, bg=CARD, fg=MUTED, font=(FONT, 9)).pack(anchor="w", pady=(6, 0))
                grid = tk.Frame(box, bg=CARD)
                grid.pack(fill="x")
                for i, n in enumerate(res.get(key, [])):
                    hit = n in mine
                    tk.Label(grid, text=n, bg=GOLD if hit else BG, fg=DARK if hit else INK,
                             font=("Consolas", 11, "bold" if hit else "normal"), width=5,
                             pady=1).grid(row=i // 5, column=i % 5, padx=2, pady=2)

            tk.Label(box, text="开奖前 V2 推荐对奖", bg=CARD, fg=GOLD2,
                     font=(FONT, 10, "bold")).pack(anchor="w", pady=(10, 2))
            if lc.get("result"):
                for x in lc["result"]:
                    msg = x["prize"] or (f"iBox 中（{x['ibox']}）" if x["ibox"] else "没中")
                    color = GOLD2 if x["prize"] or x["ibox"] else MUTED
                    tk.Label(box, text=f"{x['num']}   {msg}", bg=CARD, fg=color,
                             font=("Consolas", 11)).pack(anchor="w")
            else:
                tk.Label(box, text="（等下一期开奖后显示）", bg=CARD, fg=MUTED).pack(anchor="w")

        lotto = tk.Frame(f, bg=CARD, highlightbackground=LINE, highlightthickness=1, padx=10, pady=8)
        lotto.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(10, 0))
        tk.Label(lotto, text="Sports Toto Jackpot", bg=CARD, fg=GOLD2,
                 font=(FONT, 12, "bold")).grid(row=0, column=0, sticky="w", columnspan=8)
        for i, t in enumerate(r["lotto"].values()):
            tk.Label(lotto, text=f"{t['name']}  ({t['last_draw']})", bg=CARD, fg=INK, font=(FONT, 10),
                     width=30, anchor="w").grid(row=i + 1, column=0, sticky="w", pady=2)
            for j, b in enumerate(t.get("last_result") or []):
                tk.Label(lotto, text=f"{b:02d}", bg=GOLD, fg=DARK, font=("Consolas", 12, "bold"),
                         width=3).grid(row=i + 1, column=j + 1, padx=2, pady=2)

    def render_calc(r):
        f = ttk.Frame(nb, padding=12)
        nb.add(f, text="计算")
        comps = {c["name"]: k for k, c in r["companies"].items()}
        meths = {m["name"]: m for m in r.get("methods", [])}

        row = ttk.Frame(f)
        row.pack(fill="x")
        ttk.Label(row, text="公司").pack(side="left")
        comp = ttk.Combobox(row, values=list(comps), state="readonly", width=18)
        comp.current(0)
        comp.pack(side="left", padx=(6, 18))
        ttk.Label(row, text="计算方式").pack(side="left")
        meth = ttk.Combobox(row, values=list(meths), state="readonly", width=20)
        meth.current(0)
        meth.pack(side="left", padx=6)
        go = ttk.Button(row, text="计算")
        go.pack(side="left", padx=12)

        desc = ttk.Label(f, text="", style="Muted.TLabel", wraplength=960, padding=(0, 10))
        desc.pack(anchor="w")
        res = ttk.Frame(f)
        res.pack(fill="x")

        def show_desc(_=None):
            desc.config(text=f"{meth.get()}：{meths[meth.get()]['desc']}")

        def calc():
            show_desc()
            for w in res.winfo_children():
                w.destroy()
            m = meths[meth.get()]
            picks = r["companies"][comps[comp.get()]].get("methods", {}).get(m["id"], [])
            for p in picks:
                o = analyze.odds_4d(p["num"])
                box = ttk.Frame(res, padding=(0, 6))
                box.pack(fill="x")
                ttk.Label(box, text=p["num"], font=("Consolas", 26, "bold"),
                          foreground=GOLD2, width=6).pack(side="left")
                ttk.Label(box, text=f"{p['why']}\n头奖 {pct(o['first'])}   任何奖 {pct(o['any'])}   "
                                    f"iBox({o['perms']}组) {pct(o['ibox_any'])}",
                          justify="left").pack(side="left", padx=10)

        go.config(command=calc)
        meth.bind("<<ComboboxSelected>>", show_desc)
        show_desc()

    busy = {"on": False, "last": None}

    def do_update(silent=False):
        if busy["on"]:
            return
        busy["on"] = True
        busy["last"] = datetime.now()
        btn.state(["disabled"])

        def prog(i, n, c, d):
            root.after(0, lambda: (bar.config(maximum=n, value=i),
                                   status.config(text=f"检查新开奖 {i}/{n}  {c} {d}")))

        def done(added, r):
            now = datetime.now().strftime("%H:%M")
            if r:
                render(r)
                status.config(text=status.cget("text") + f"   新增 {added} 期（{now}）")
                nb.select(0)
            else:
                status.config(text=f"没有新开奖（检查于 {now}）")

        def work():
            try:
                added, r = run_update(prog)
                root.after(0, lambda: done(added, r))
            except Exception as e:
                if not silent:
                    root.after(0, lambda: messagebox.showerror("更新失败", str(e)))
            finally:
                busy["on"] = False
                root.after(0, lambda: btn.state(["!disabled"]))

        threading.Thread(target=work, daemon=True).start()

    def refresh_live():
        def work():
            changed, live = save_live()
            if live:
                state["live"] = live
            if changed and state["r"]:
                root.after(0, lambda: (render(state["r"]), nb.select(0)))
        threading.Thread(target=work, daemon=True).start()

    def auto_tick():
        """开奖时间（晚上 7-9 点）：每分钟看实时成绩，每 5 分钟完整更新一次。"""
        now = datetime.now()
        if auto.get() and 19 <= now.hour < 21:
            refresh_live()
            if busy["last"] is None or (now - busy["last"]).total_seconds() >= 300:
                do_update(silent=True)
        root.after(60_000, auto_tick)

    btn.config(command=do_update)
    if LIVE_PATH.exists():
        state["live"] = json.loads(LIVE_PATH.read_text("utf-8"))
    render(load_result())
    refresh_live()
    root.after(5_000, auto_tick)
    root.mainloop()


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "update":
        cli_update()
    elif cmd == "serve":
        cli_serve(int(sys.argv[2]) if len(sys.argv) > 2 else 8000)
    else:
        gui()
