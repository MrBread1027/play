"""抓取 Magnum / Da Ma Cai / Sports Toto 开奖资料（只用标准库）。

来源:
  Magnum    - magnum4d.my 官方 JSON 接口
  Da Ma Cai - damacai.com.my 官方 JSON 接口
  Toto      - 4dmoon.com (Sports Toto 官网拒绝程序访问)
"""
import html
import json
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"}
COMPANIES = ("magnum", "damacai", "toto")


def _get(url, headers=None, retries=3):
    h = dict(UA, **(headers or {}))
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=30) as r:
                return r.read().decode("utf-8", "ignore")
        except Exception:
            if i == retries - 1:
                raise
            time.sleep(1.5 * (i + 1))


def _clean(nums):
    return [n for n in nums if re.fullmatch(r"\d{4}", n or "")]


# ---------------------------------------------------------------- 开奖日期
def draw_dates():
    """Da Ma Cai 提供所有开奖日期（西马三家公司同日开奖）。"""
    d = json.loads(_get("https://www.damacai.com.my/ListPastResult"))["drawdate"].split()
    return [datetime.strptime(x, "%Y%m%d").date() for x in d]


# ---------------------------------------------------------------- Magnum
def fetch_magnum(d: date):
    s = d.strftime("%m-%d-%Y")
    rows = json.loads(_get(f"https://www.magnum4d.my/results/past/between-dates/{s}/{s}") or "[]")
    for r in rows:
        if datetime.strptime(r["DrawDate"], "%d/%m/%Y").date() == d:
            return {
                "top3": _clean([r["FirstPrize"], r["SecondPrize"], r["ThirdPrize"]]),
                "special": _clean([r[f"Special{i}"] for i in range(1, 11)]),
                "consolation": _clean([r[f"Console{i}"] for i in range(1, 11)]),
            }
    return None


# ---------------------------------------------------------------- Da Ma Cai
def fetch_damacai(d: date):
    h = {"cookiesession": "299"}
    link = json.loads(_get(f"https://www.damacai.com.my/callpassresult?pastdate={d:%Y%m%d}", h))["link"]
    r = json.loads(_get(link))
    if not r or r.get("status") != "COMPLETED":
        return None
    return {
        "top3": _clean([r["p1"], r["p2"], r["p3"]]),
        "special": _clean(r.get("starterList", [])),
        "consolation": _clean(r.get("consolidateList", [])),
    }


# ---------------------------------------------------------------- Sports Toto (4dmoon)
def _cells(block, cls):
    return [html.unescape(x).strip() for x in re.findall(rf'class="{cls}"[^>]*>([^<]*)<', block)]


def fetch_toto(d: date):
    page = _get(f"https://www.4dmoon.com/past-results/{d:%Y-%m-%d}")
    want = d.strftime("%d-%b-%Y")

    def section(title, end_titles):
        i = page.find(title)
        if i < 0:
            return None
        j = min([k for k in (page.find(t, i + len(title)) for t in end_titles) if k > 0] or [len(page)])
        blk = page[i:j]
        return blk if want in blk else None

    out = {}
    blk = section("SportsToto 4D", ["SportsToto 5D", "Damacai", "Magnum"])
    if blk:
        top = _cells(blk, "rtn")[:3]
        rest = blk.split(">Consolation<")
        out.update(top3=_clean(top),
                   special=_clean(_cells(rest[0], "rbn")),
                   consolation=_clean(_cells(rest[1], "rbn")) if len(rest) > 1 else [])
    blk = section("SportsToto Lotto", ["Damacai", "Magnum", "Sandakan"])
    if blk:
        for key, title in (("t650", "Star Toto 6/50"), ("t655", "Power Toto 6/55"), ("t658", "Supreme Toto 6/58")):
            i = blk.find(title)
            if i < 0:
                continue
            sub = blk[i:blk.find("Jackpot", i)]
            nums = [int(x) for x in re.findall(r'class="rto2?"[^>]*>(\d{1,2})<', sub)]
            if len(nums) >= 6:
                out[key] = sorted(nums[:6])
    return out or None


def complete(r):
    """开奖进行中时结果是一个一个公布的，只有全部公布完才保存。"""
    return (len(r.get("top3", [])) == 3 and len(r.get("special", [])) >= 10
            and len(r.get("consolation", [])) == 10)


# ---------------------------------------------------------------- 实时成绩 (4dmoon 首页用的 feed)
LIVE_KEYS = {"magnum": "M", "damacai": "D", "toto": "T"}


def fetch_live():
    """最新一期（包括正在开奖中）的成绩: {company: {date, draw_no, live, top3, special, consolation}}"""
    feed = json.loads(_get("https://www.4dmoon.com/feedwest.json"))
    out = {}
    for c, k in LIVE_KEYS.items():
        r = feed.get(k) or {}
        m = re.search(r"(\d{2}-[A-Za-z]{3}-\d{4})", r.get("DD", ""))
        if not m:
            continue
        out[c] = {
            "date": datetime.strptime(m.group(1), "%d-%b-%Y").date().isoformat(),
            "draw_no": r.get("DN", "").lstrip("#"),
            "live": r.get("LS", "0") != "0",
            "top3": [r.get(f"P{i}", "") for i in (1, 2, 3)],
            "special": _clean([r.get(f"S{i}") for i in range(1, 14)]),
            "consolation": _clean([r.get(f"C{i}") for i in range(1, 11)]),
        }
    return out


def _toto_with_live(d: date):
    """4dmoon 的 past-results 通常隔一段时间才有当天资料，先用实时 feed 补上 4D。"""
    r = fetch_toto(d)
    if r and complete(r):
        return r
    try:
        live = fetch_live().get("toto")
    except Exception:
        return r
    if live and live["date"] == d.isoformat() and not live["live"]:
        res = {k: live[k] for k in ("top3", "special", "consolation")}
        res["top3"] = _clean(res["top3"])
        return {**(r or {}), **res}
    return r


FETCHERS = {"magnum": fetch_magnum, "damacai": fetch_damacai, "toto": _toto_with_live}


# ---------------------------------------------------------------- 增量更新
def update(db: dict, years=3, progress=None, workers=4):
    """把最近 `years` 年缺少的开奖补进 db，返回新增数量。

    db 结构: {"magnum": {"2025-09-03": {...}}, "damacai": {...}, "toto": {...}}
    """
    today = date.today()
    start = today - timedelta(days=365 * years + 7)
    dates = {d for d in draw_dates() if start <= d <= today}
    # 开奖当晚 Da Ma Cai 的日期清单可能还没更新，先把今天(周三/六/日)加进去
    if today.weekday() in (2, 5, 6):
        dates.add(today)
    dates = sorted(dates)
    for c in COMPANIES:
        db.setdefault(c, {})
        # 删除超出窗口的旧资料
        for k in [k for k in db[c] if k < start.isoformat()]:
            del db[c][k]

    jobs = [(c, d) for d in dates for c in COMPANIES if d.isoformat() not in db[c]]
    # Toto 4D 先从实时 feed 补上的那几期，3 天内再回头补 6/50·55·58
    jobs += [("toto", d) for d in dates if (today - d).days <= 3
             and db["toto"].get(d.isoformat()) and "t650" not in db["toto"][d.isoformat()]]
    done = added = 0

    def run(job):
        c, d = job
        try:
            return c, d, FETCHERS[c](d)
        except Exception as e:  # 单期失败不影响整体
            return c, d, e

    with ThreadPoolExecutor(workers) as ex:
        for c, d, res in ex.map(run, jobs):
            done += 1
            if isinstance(res, dict) and complete(res):
                is_new = d.isoformat() not in db[c] or res != db[c][d.isoformat()]
                db[c][d.isoformat()] = {**db[c].get(d.isoformat(), {}), **res}
                added += is_new
            elif res is None and (today - d).days > 3:
                # 确认当日没有开奖，记下以免每次重抓
                db[c][d.isoformat()] = {}
            if progress:
                progress(done, len(jobs), c, d)
    return added
