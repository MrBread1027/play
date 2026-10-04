"""统计分析 + 推荐号码 + 真实中奖概率 + 历史回测。

重要: 每期开奖是独立随机的。推荐号码只是"过去出现较多"的号码，
真实中奖概率由游戏规则决定，不会因为历史频率而改变。回测结果用来验证这一点。
"""
import heapq
from collections import Counter, deque
from datetime import datetime
from itertools import permutations
from math import comb

from . import engine, methods

NAMES = {"magnum": "Magnum 4D", "damacai": "Da Ma Cai 1+3D", "toto": "Sports Toto 4D"}
JACKPOT_NAMES = {"magnum": "Magnum 4D Jackpot", "damacai": "Da Ma Cai 1+3D Jackpot",
                 "toto": "Toto 4D Jackpot"}
LOTTO = {"t650": ("Star Toto 6/50", 50), "t655": ("Power Toto 6/55", 55),
         "t658": ("Supreme Toto 6/58", 58)}

RECENT = 78        # 约半年的期数，近期出现的权重更高
TOP_N = 4
BACKTEST = 150     # 回测最近多少期
PRIZES_4D = 23     # 1st/2nd/3rd + 10 special + 10 consolation


def _numbers(draw):
    return draw.get("top3", []) + draw.get("special", []) + draw.get("consolation", [])


def perms(num):
    return len(set(permutations(num)))


def _one_in(p):
    return round(1 / p) if p else None


def odds_4d(num):
    """单个 4D 号码（RM1 Big）的真实概率。"""
    k = perms(num)
    return {
        "first": 1 / 10000,
        "any": PRIZES_4D / 10000,
        "ibox_any": min(1.0, PRIZES_4D * k / 10000),
        "perms": k,
    }


JACKPOT_PAIR_P = 3 / comb(10000, 2)   # 两个号码同时中 1st/2nd/3rd 中任意两个


# ---------------------------------------------------------------- 4D
def _rank(total: Counter, recent: Counter, last_seen: dict, n):
    def key(num):
        return (total[num] + 2 * recent[num], last_seen.get(num, ""))
    return heapq.nlargest(n, total.keys(), key=key)


def analyze_4d(draws: dict):
    dates = sorted(d for d, v in draws.items() if v.get("top3"))
    total, recent, last_seen = Counter(), Counter(), {}
    window = deque()
    pos = [Counter() for _ in range(4)]
    bt_hits = bt_n = 0
    bt_from = len(dates) - BACKTEST

    for i, d in enumerate(dates):
        nums = _numbers(draws[d])
        # 回测: 用这一期之前的资料选号，再看这一期有没有中
        if i >= bt_from and i >= 100:
            picks = _rank(total, recent, last_seen, TOP_N)
            bt_hits += len(set(picks) & set(nums))
            bt_n += 1
        total.update(nums)
        recent.update(nums)
        window.append(nums)
        if len(window) > RECENT:
            recent.subtract(window.popleft())
        for n in nums:
            last_seen[n] = d
            for p, ch in enumerate(n):
                pos[p][ch] += 1

    picks = []
    for num in _rank(total, recent, last_seen, TOP_N):
        picks.append({
            "num": num,
            "count": total[num],
            "recent": recent[num],
            "last_seen": last_seen.get(num),
            "hist_rate": total[num] / len(dates) if dates else 0,
            "odds": odds_4d(num),
        })

    digit_pick = "".join(c.most_common(1)[0][0] if c else "0" for c in pos)
    jp = [p["num"] for p in picks[:2]]
    return {
        "draws": len(dates),
        "first_draw": dates[0] if dates else None,
        "last_draw": dates[-1] if dates else None,
        "last_result": draws[dates[-1]] if dates else None,
        "picks": picks,
        "digit_pick": {"num": digit_pick, "odds": odds_4d(digit_pick)},
        "digit_freq": [{str(k): v for k, v in sorted(c.items())} for c in pos],
        "methods": methods.compute(dates, draws, total, recent, last_seen) if dates else {},
        "v2": engine.run(dates, draws, seed=len(dates)) if len(dates) > engine.TEST_START else None,
        "jackpot": {"pair": jp, "p": JACKPOT_PAIR_P, "one_in": _one_in(JACKPOT_PAIR_P)},
        "backtest": {
            "draws": bt_n,
            "picks_per_draw": TOP_N,
            "hits": bt_hits,
            "hit_rate": bt_hits / (bt_n * TOP_N) if bt_n else 0,
            "random_rate": PRIZES_4D / 10000,
        },
    }


# ---------------------------------------------------------------- Toto 6/xx
def analyze_lotto(draws: dict, key: str, n_balls: int):
    dates = sorted(d for d, v in draws.items() if v.get(key))
    freq, last_seen = Counter(), {}
    bt_match = bt_n = 0
    for i, d in enumerate(dates):
        balls = draws[d][key]
        if i >= len(dates) - BACKTEST and i >= 50:
            hot = [b for b, _ in freq.most_common(6)]
            bt_match += len(set(hot) & set(balls))
            bt_n += 1
        freq.update(balls)
        for b in balls:
            last_seen[b] = i
    allb = range(1, n_balls + 1)
    hot = sorted(allb, key=lambda b: (-freq[b], -last_seen.get(b, -1)))
    gap = {b: len(dates) - 1 - last_seen.get(b, -1) for b in allb}
    cold = sorted(allb, key=lambda b: -gap[b])
    mix = sorted(set(hot[:4]) | set(cold[:2]))
    p = 1 / comb(n_balls, 6)
    return {
        "draws": len(dates),
        "last_draw": dates[-1] if dates else None,
        "last_result": draws[dates[-1]][key] if dates else None,
        "hot_pick": sorted(hot[:6]),
        "mix_pick": mix if len(mix) == 6 else sorted(hot[:6]),
        "freq": [{"ball": b, "count": freq[b], "gap": gap[b]} for b in hot],
        "p": p,
        "one_in": _one_in(p),
        "backtest": {
            "draws": bt_n,
            "avg_match": bt_match / bt_n if bt_n else 0,
            "random_match": 36 / n_balls,
        },
    }


def build(db: dict):
    out = {"updated": datetime.now().isoformat(timespec="minutes"), "companies": {}, "lotto": {},
           "methods": [{"id": "v2", "name": "V2 综合评分",
                        "desc": "Prediction Engine V2：长短期频率、位置、数字对、遗漏值、模式、机器学习加权综合，"
                                "并过滤极端组合。回测结果见各公司页面。"}]
                      + [{"id": i, "name": n, "desc": d} for i, n, d in methods.METHODS]}
    for c, name in NAMES.items():
        r = analyze_4d(db.get(c, {}))
        r["name"] = name
        r["jackpot"]["name"] = JACKPOT_NAMES[c]
        if r.get("v2"):
            r["jackpot"]["pair"] = [p["num"] for p in r["v2"]["picks"][:2]]
            r["methods"]["v2"] = [{"num": p["num"], "why": f"综合评分 {p['score']}（平均号码为 50）"}
                                  for p in r["v2"]["top3"]]
        out["companies"][c] = r
    for key, (name, n) in LOTTO.items():
        r = analyze_lotto(db.get("toto", {}), key, n)
        r["name"] = name
        r["balls"] = n
        out["lotto"][key] = r
    return out
