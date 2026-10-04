"""马来西亚 4D / Jackpot 号码分析器 - Python 版

用法:
  python app.py            打开电脑版界面
  python app.py update     更新资料并重新计算（无界面，给自动排程用）
  python app.py serve      在本机开网页版 (手机同一 WiFi 可访问)
"""
import json
import socket
import sys
import threading
from pathlib import Path

from lotto import analyze, fetch

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "draws.json"
OUT_PATH = ROOT / "web" / "data.json"

DISCLAIMER = ("提醒：每期开奖都是独立随机的。推荐号码只是过去三年出现较多的号码，"
              "真实中奖概率由游戏规则决定，不会因为历史资料而提高。请理性投注。")


def load_db():
    return json.loads(DB_PATH.read_text("utf-8")) if DB_PATH.exists() else {}


def save(db, result):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(db, separators=(",", ":")), "utf-8")
    OUT_PATH.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), "utf-8")


def run_update(progress=None):
    db = load_db()
    added = fetch.update(db, progress=progress)
    result = analyze.build(db)
    save(db, result)
    return added, result


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
    added, r = run_update(prog)
    print(f"新增 {added} 期。")
    for c in r["companies"].values():
        print(f"{c['name']:<16} {c['draws']} 期, 推荐: {' '.join(p['num'] for p in c['picks'][:5])}")
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

    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    ttk.Label(top, text="4D 号码分析 V2", style="Title.TLabel").pack(side="left", padx=(0, 16))
    btn = ttk.Button(top, text="更新资料")
    btn.pack(side="left")
    status = ttk.Label(top, text="")
    status.pack(side="left", padx=12)
    bar = ttk.Progressbar(top, length=220)
    bar.pack(side="right")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8)
    ttk.Label(root, text=DISCLAIMER, foreground="#f0b47a", wraplength=1000,
              padding=8).pack(fill="x")

    def render(r):
        for t in nb.tabs():
            nb.forget(t)
        if not r:
            status.config(text="还没有资料，请按「更新资料」（第一次约需 5-10 分钟）")
            return
        status.config(text=f"最后更新: {r['updated'].replace('T', ' ')}")
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

    def do_update():
        btn.state(["disabled"])

        def prog(i, n, c, d):
            root.after(0, lambda: (bar.config(maximum=n, value=i),
                                   status.config(text=f"下载中 {i}/{n}  {c} {d}")))

        def work():
            try:
                added, r = run_update(prog)
                root.after(0, lambda: (render(r), status.config(
                    text=status.cget("text") + f"   (新增 {added} 期)")))
            except Exception as e:
                root.after(0, lambda: messagebox.showerror("更新失败", str(e)))
            finally:
                root.after(0, lambda: btn.state(["!disabled"]))

        threading.Thread(target=work, daemon=True).start()

    btn.config(command=do_update)
    render(load_result())
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
