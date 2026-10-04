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

    root = tk.Tk()
    root.title("4D 号码分析器 - Magnum / Da Ma Cai / Toto")
    root.geometry("980x640")
    style = ttk.Style()
    style.configure("Treeview", rowheight=26, font=("Segoe UI", 10))
    style.configure("Big.TLabel", font=("Segoe UI", 12, "bold"))

    top = ttk.Frame(root, padding=8)
    top.pack(fill="x")
    btn = ttk.Button(top, text="更新资料")
    btn.pack(side="left")
    status = ttk.Label(top, text="")
    status.pack(side="left", padx=12)
    bar = ttk.Progressbar(top, length=220)
    bar.pack(side="right")

    nb = ttk.Notebook(root)
    nb.pack(fill="both", expand=True, padx=8)
    ttk.Label(root, text=DISCLAIMER, foreground="#a33", wraplength=940,
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
            f = ttk.Frame(nb, padding=10)
            nb.add(f, text=c["name"])
            ttk.Label(f, text=f"{c['name']}  ·  分析 {c['draws']} 期 "
                              f"({c['first_draw']} 至 {c['last_draw']})", style="Big.TLabel").pack(anchor="w")
            cols = ("num", "count", "recent", "last", "first", "any", "ibox")
            heads = ("推荐号码", "3年出现次数", "近半年", "最后出现", "头奖概率",
                     "任何奖概率 (Big)", "iBox 任何奖概率")
            tv = ttk.Treeview(f, columns=cols, show="headings", height=4)
            for col, h in zip(cols, heads):
                tv.heading(col, text=h)
                tv.column(col, width=150 if col in ("first", "any", "ibox") else 95, anchor="center")
            for p in c["picks"]:
                o = p["odds"]
                tv.insert("", "end", values=(p["num"], p["count"], p["recent"], p["last_seen"],
                                             pct(o["first"]), pct(o["any"]),
                                             f"{pct(o['ibox_any'])} ×{o['perms']}"))
            tv.pack(fill="x", pady=8)
            dp = c["digit_pick"]
            jp = c["jackpot"]
            bt = c["backtest"]
            info = (f"位数频率组合号码: {dp['num']}    任何奖概率 {pct(dp['odds']['any'])}\n"
                    f"{jp['name']} 推荐组合: {' + '.join(jp['pair'])}    "
                    f"Jackpot 1 概率 约 1/{jp['one_in']:,}\n"
                    f"历史回测（最近 {bt['draws']} 期，每期买前 {bt['picks_per_draw']} 个推荐号）: "
                    f"命中率 {bt['hit_rate'] * 100:.2f}%，纯随机应为 {bt['random_rate'] * 100:.2f}%")
            ttk.Label(f, text=info, justify="left").pack(anchor="w")

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

        desc = ttk.Label(f, text="", foreground="#666", wraplength=900, padding=(0, 10))
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
                          foreground="#8b1a1a", width=6).pack(side="left")
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
