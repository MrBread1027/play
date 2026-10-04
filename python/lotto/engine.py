"""4D Prediction Engine V2 —— 综合评分 + 机器学习 + 严格 Walk-forward 回测。

流程:
  历史资料 → 长/短期频率 → 位置频率 → 数字对(Pair) → 遗漏值(Gap) → 模式(Pattern)
  → 逻辑回归(ML) → 综合评分 → 过滤极端组合 → Walk-forward 回测 → 校准

每一期都只用"当时之前"的资料打分，再拿当期结果检验，模型从来没有偷看未来。
校准后的概率来自回测的真实命中率，而不是模型自称的 confidence。
"""
import heapq
import math
import random
from collections import Counter, deque

N = 10000
NUMS = [f"{i:04d}" for i in range(N)]
DIGS = [tuple(int(c) for c in n) for n in NUMS]
COL = [[d[p] for d in DIGS] for p in range(4)]
PAIRS = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
PAIR_IDX = [[d[a] * 10 + d[b] for d in DIGS] for a, b in PAIRS]

_PAT = {(1, 1, 1, 1): "ABCD", (2, 1, 1): "AABC", (2, 2): "AABB", (3, 1): "AAAB", (4,): "AAAA"}
PAT = [_PAT[tuple(sorted(Counter(d).values(), reverse=True))] for d in DIGS]
PAT_SIZE = Counter(PAT)
SUMS = [sum(d) for d in DIGS]
ODD = [sum(x & 1 for x in d) for d in DIGS]
BIG = [sum(x >= 5 for x in d) for d in DIGS]

FEATURES = ["long", "short", "pos", "pair", "gap", "pattern"]
WEIGHTS = {"long": .20, "short": .20, "pos": .15, "pair": .15, "gap": .10, "pattern": .10, "ml": .10}
LABELS = {"long": "长期频率", "short": "近期频率", "pos": "位置频率", "pair": "数字对",
          "gap": "遗漏值", "pattern": "模式", "ml": "机器学习"}

SHORT = 78         # 近期窗口 ≈ 半年
ML_START = 100     # 前 100 期只累积资料
TEST_START = 150   # 第 150 期开始 walk-forward 回测
KS = (4, 10, 20, 50, 100)


def _z(xs):
    n = len(xs)
    m = sum(xs) / n
    v = sum((x - m) ** 2 for x in xs) / n
    if v <= 1e-12:
        return [0.0] * n
    s = v ** .5
    return [(x - m) / s for x in xs]


class State:
    """截至某一期为止的所有统计量（增量更新）。"""

    def __init__(self):
        self.t = 0
        self.total = 0
        self.long = [0] * N
        self.short = [0] * N
        self.window = deque()
        self.last = [-1] * N
        self.pos = [[0] * 10 for _ in range(4)]
        self.pair = [[0] * 100 for _ in PAIRS]
        self.pat = Counter()
        self.sums = Counter()

    def add(self, idxs):
        for i in idxs:
            d = DIGS[i]
            self.long[i] += 1
            self.short[i] += 1
            self.last[i] = self.t
            for p in range(4):
                self.pos[p][d[p]] += 1
            for k, (a, b) in enumerate(PAIRS):
                self.pair[k][d[a] * 10 + d[b]] += 1
            self.pat[PAT[i]] += 1
            self.sums[SUMS[i]] += 1
        self.total += len(idxs)
        self.window.append(idxs)
        if len(self.window) > SHORT:
            for i in self.window.popleft():
                self.short[i] -= 1
        self.t += 1

    def features(self):
        """每个号码 6 个特征，全部标准化成 z 分数。"""
        tot = self.total or 1
        f = {"long": self.long, "short": self.short}
        pos_lr = [[math.log((c + 1) / (tot / 10 + 1)) for c in self.pos[p]] for p in range(4)]
        cols = [[lr[d] for d in COL[p]] for p, lr in enumerate(pos_lr)]
        f["pos"] = [a + b + c + d for a, b, c, d in zip(*cols)]
        pair_lr = [[math.log((c + 1) / (tot / 100 + 1)) for c in pc] for pc in self.pair]
        pcols = [[lr[x] for x in PAIR_IDX[k]] for k, lr in enumerate(pair_lr)]
        f["pair"] = [sum(v) for v in zip(*pcols)]
        cap = max(self.t, 1)
        f["gap"] = [(self.t - l if l >= 0 else cap) / cap for l in self.last]
        pat_lr = {k: math.log((self.pat[k] + 1) / (tot * PAT_SIZE[k] / N + 1)) for k in PAT_SIZE}
        f["pattern"] = [pat_lr[p] for p in PAT]
        return {k: _z(v) for k, v in f.items()}

    def sum_range(self):
        """历史中奖号码数字和的 2%–98% 范围。"""
        tot = sum(self.sums.values())
        if not tot:
            return 0, 36
        cum, lo, hi = 0, None, 36
        for s in range(37):
            cum += self.sums[s]
            if lo is None and cum / tot >= .02:
                lo = s
            if cum / tot <= .98:
                hi = s + 1
        return lo or 0, hi

    def mask(self):
        """过滤极端组合：数字和太极端、AAAA、全奇/全偶且全大/全小。"""
        lo, hi = self.sum_range()
        return [lo <= SUMS[i] <= hi and PAT[i] != "AAAA"
                and not (ODD[i] in (0, 4) and BIG[i] in (0, 4)) for i in range(N)]


class LogReg:
    """在线逻辑回归：每期开奖后用中奖号码(正例)和随机抽样的未中号码(负例)更新。"""

    def __init__(self, n, lr=.03, l2=1e-3):
        self.w = [0.0] * n
        self.b = 0.0
        self.lr, self.l2 = lr, l2

    def logits(self, X):
        w, b = self.w, self.b
        return [b + sum(wk * x for wk, x in zip(w, row)) for row in zip(*X)]

    def train(self, X, pos, rng, neg=230):
        negs = [i for i in rng.sample(range(N), neg + len(pos)) if i not in pos][:neg]
        samples = [(i, 1) for i in pos] + [(i, 0) for i in negs]
        rng.shuffle(samples)
        for i, y in samples:
            x = [col[i] for col in X]
            z = self.b + sum(wk * xk for wk, xk in zip(self.w, x))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            g = p - y
            self.w = [wk - self.lr * (g * xk + self.l2 * wk) for wk, xk in zip(self.w, x)]
            self.b -= self.lr * g


def _ensemble(Z, mlz, mask):
    cols = [Z[k] for k in FEATURES] + [mlz]
    ws = [WEIGHTS[k] for k in FEATURES] + [WEIGHTS["ml"]]
    return [sum(w * c for w, c in zip(ws, row)) if ok else -1e9
            for row, ok in zip(zip(*cols), mask)]


def _poisson_tail(k, lam):
    """P(X >= k)，X ~ Poisson(lam)。用来判断命中数是否显著高于随机。"""
    if k <= 0:
        return 1.0
    term = math.exp(-lam)
    cdf = term
    for j in range(1, k):
        term *= lam / j
        cdf += term
    return max(0.0, 1 - cdf)


def _wilson(h, n, z=1.96):
    if not n:
        return 0, 0
    p = h / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0, c - r), c + r


def run(dates, draws, seed=0, top=4):
    st = State()
    ml = LogReg(len(FEATURES))
    rng = random.Random(seed)
    bt = {K: {"hits": 0, "first": 0, "draws_hit": 0} for K in KS}
    T = 0
    distinct = 0
    prev = None   # 最新一期开奖前 V2 推荐的号码，用来对奖

    for t, d in enumerate(dates):
        r = draws[d]
        idxs = [int(n) for n in r["top3"] + r["special"] + r["consolation"]]
        win = set(idxs)
        first = int(r["top3"][0])
        if t >= ML_START:
            Z = st.features()
            X = [Z[k] for k in FEATURES]
            if t >= TEST_START:
                score = _ensemble(Z, _z(ml.logits(X)), st.mask())
                best = heapq.nlargest(max(KS), range(N), key=score.__getitem__)
                for K in KS:
                    h = sum(1 for i in best[:K] if i in win)
                    bt[K]["hits"] += h
                    bt[K]["draws_hit"] += h > 0
                    bt[K]["first"] += first in best[:K]
                T += 1
                distinct += len(win)
                if t == len(dates) - 1:
                    prev = {"date": d, "picks": [NUMS[i] for i in best[:top]]}
            ml.train(X, win, rng)
        st.add(idxs)

    # ---- 用全部资料为下一期打分
    Z = st.features()
    X = [Z[k] for k in FEATURES]
    mlz = _z(ml.logits(X))
    mask = st.mask()
    score = _ensemble(Z, mlz, mask)
    valid = [s for s in score if s > -1e8]
    mu = sum(valid) / len(valid)
    sd = (sum((s - mu) ** 2 for s in valid) / len(valid)) ** .5 or 1
    ranked = heapq.nlargest(max(top, 3), range(N), key=score.__getitem__)

    def t_score(s):    # 标准分：50 = 平均，每高一个标准差 +10
        return 50 + 10 * (s - mu) / sd

    picks = []
    for i in ranked:
        parts = {k: round(WEIGHTS[k] * Z[k][i], 3) for k in FEATURES}
        parts["ml"] = round(WEIGHTS["ml"] * mlz[i], 3)
        picks.append({"num": NUMS[i], "score": round(t_score(score[i]), 1),
                      "raw": round(score[i], 3), "parts": parts,
                      "count": st.long[i], "recent": st.short[i], "pattern": PAT[i]})

    rand = distinct / T / N if T else 23 / N
    rows = []
    for K in KS:
        b = bt[K]
        n = K * T
        exp = n * rand
        rows.append({
            "k": K, "hits": b["hits"], "expected": round(exp, 2),
            "rate": b["hits"] / n if n else 0, "random_rate": rand,
            "draws_hit": b["draws_hit"],
            "draws_hit_expected": round(T * (1 - (1 - rand) ** K), 1),
            "first": b["first"], "first_expected": round(T * K / N, 2),
            "p_value": _poisson_tail(b["hits"], exp),
        })
    b4 = bt[KS[0]]
    lo, hi = _wilson(b4["hits"], KS[0] * T)
    lo_s, hi_s = st.sum_range()
    return {
        "picks": picks[:top],
        "top3": picks[:3],
        "last_check": prev,
        "backtest": {"draws": T, "train_from": dates[0] if dates else None,
                     "test_from": dates[TEST_START] if len(dates) > TEST_START else None,
                     "rows": rows,
                     "calibrated": {"rate": b4["hits"] / (KS[0] * T) if T else 0,
                                    "lo": lo, "hi": hi, "random": rand}},
        "weights": WEIGHTS,
        "labels": LABELS,
        "ml_weights": {k: round(w, 3) for k, w in zip(FEATURES, ml.w)},
        "filters": {"sum_lo": lo_s, "sum_hi": hi_s, "kept": sum(mask)},
    }
