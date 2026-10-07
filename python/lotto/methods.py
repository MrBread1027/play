"""网上流行的 4D 选号计算方法。每个方法按公司资料算出 3 个号码。

这些方法在玩家之间很流行，但都没有经过验证的预测能力。
"""
from collections import Counter, defaultdict

MIRROR = str.maketrans("0123456789", "5678901234")   # 对数: 0↔5 1↔6 2↔7 3↔8 4↔9

METHODS = [
    ("hot", "热号法", "十年里出现次数最多的号码（近半年出现的加倍计算）。"),
    ("cold", "冷号法（久未出现）", "以前常开、但最久没有再出现的号码，玩家认为“该轮到它了”。"),
    ("digit", "位数频率法", "千、百、十、个位分别统计最常出现的数字，组合成号码。"),
    ("mirror", "对数法（阴阳数）", "把上期头三奖每个数字换成对数：0↔5、1↔6、2↔7、3↔8、4↔9。"),
    ("follow", "拖号法（跟号）", "看历史上每当某个数字开出后，下一期同一位置最常跟着开什么数字。"),
    ("tail3d", "3D 热门尾数法", "找出最常开的后三位（3D），再配上最常一起出现的千位数字。"),
    ("sum", "和值法", "四个数字加起来的总和，选最常见的和值里出现最多的号码。"),
    ("formula", "头奖加减公式", "上期头奖每位数字 +1、-1，以及前后倒转。"),
]


def _shift(num, k):
    return "".join(str((int(d) + k) % 10) for d in num)


def compute(dates, draws, total, recent, last_seen):
    """dates: 已排序日期; draws: {date: {...}}; total/recent: Counter; last_seen: {num: date}"""
    def nums(d):
        r = draws[d]
        return r["top3"] + r["special"] + r["consolation"]

    last_d = dates[-1]
    last = draws[last_d]["top3"]
    idx = {d: i for i, d in enumerate(dates)}
    out = {}

    # 热号
    hot = sorted(total, key=lambda n: (total[n] + 2 * recent[n], last_seen[n]), reverse=True)[:3]
    out["hot"] = [(n, f"十年出现 {total[n]} 次，近半年 {recent[n]} 次") for n in hot]

    # 冷号: 至少出现过 3 次，距离上次出现最久
    pool = [n for n in total if total[n] >= 3] or list(total)
    cold = sorted(pool, key=lambda n: (idx[last_seen[n]], -total[n]))[:3]
    out["cold"] = [(n, f"出现过 {total[n]} 次，已经 {len(dates) - 1 - idx[last_seen[n]]} 期没开")
                   for n in cold]

    # 位数频率
    pos = [Counter() for _ in range(4)]
    for d in dates:
        for n in nums(d):
            for p, ch in enumerate(n):
                pos[p][ch] += 1
    ranked = [[ch for ch, _ in c.most_common()] for c in pos]
    out["digit"] = [("".join(r[k] for r in ranked), f"每个位置第 {k + 1} 常见的数字") for k in range(3)]

    # 对数
    out["mirror"] = [(n.translate(MIRROR), f"上期{['头', '二', '三'][i]}奖 {n} 的对数")
                     for i, n in enumerate(last)]

    # 拖号: 统计 "这期第 p 位是 a → 下期第 p 位是 b"（用头三奖）
    trans = [defaultdict(Counter) for _ in range(4)]
    for a, b in zip(dates, dates[1:]):
        for x in draws[a]["top3"]:
            for y in nums(b):
                for p in range(4):
                    trans[p][x[p]][y[p]] += 1
    out["follow"] = []
    for i, n in enumerate(last):
        f = "".join(trans[p][n[p]].most_common(1)[0][0] if trans[p][n[p]] else n[p] for p in range(4))
        out["follow"].append((f, f"根据上期{['头', '二', '三'][i]}奖 {n} 每个位置的拖号"))

    # 3D 热门尾数
    tails = Counter(n[1:] for d in dates for n in nums(d))
    heads = defaultdict(Counter)
    for d in dates:
        for n in nums(d):
            heads[n[1:]][n[0]] += 1
    out["tail3d"] = []
    for t, cnt in tails.most_common(3):
        h = heads[t].most_common(1)[0][0]
        out["tail3d"].append((h + t, f"尾数 {t} 十年开了 {cnt} 次，千位最常配 {h}"))

    # 和值
    sums = Counter(sum(map(int, n)) for d in dates for n in nums(d))
    s, s_cnt = sums.most_common(1)[0]
    pick = sorted((n for n in total if sum(map(int, n)) == s),
                  key=lambda n: (total[n], last_seen[n]), reverse=True)[:3]
    out["sum"] = [(n, f"最常见和值是 {s}（{s_cnt} 次），这个号码出现 {total[n]} 次") for n in pick]

    # 头奖加减公式
    first = last[0]
    out["formula"] = [(_shift(first, 1), f"上期头奖 {first} 每位 +1"),
                      (_shift(first, -1), f"上期头奖 {first} 每位 -1"),
                      (first[::-1], f"上期头奖 {first} 前后倒转")]

    return {k: [{"num": n, "why": w} for n, w in v] for k, v in out.items()}
