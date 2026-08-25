#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专业冷热趋势的纯计算内核（无副作用，不选连接串、不写文件）。

被两处复用，保证「研究口径」与「入库口径」永远是同一份实现：
  - `webapp/scripts/major_trend.py`  只读研究/诊断脚本（--check/--placebo/--backtest）
  - `etl/load_major_trend.py`        全量重建 major_trend* 三表

方法（推导与验证见 docs/major-trend-2024-2026.md）
-------------------------------------------------
1. 位次百分位化  p = lowest_rank / N(year, subject)，N 取该年该学科类一分一段
   表的最大累计位次。辽宁 2025 历史类考生 +29.3%，原始位次跨年不可比。
2. 同单元配对    两趟匹配（见 pair_year）——省内专业代码是逐年重排的顺序号，
   只按代码配会把不同专业接成一条时间线。
3. 去大盘漂移    每个 (学科类,批次,年段) 取全部配对单元 δ 的中位数 m 作基准，
   超额漂移 e = δ − m。只谈 e，即「相对全省的相对冷热」。
4. 专业层聚合    本科批按 major_name_map → major_catalog 标准专业；专科批
   catalog 覆盖仅 33.6%（catalog 是本科目录），改按去括号后的原始专业名聚合。
5. 阈值          置换检验：把 e 打散随机抽 n 个算中位数，重复多次得零分布，
   取双侧 95% 分位作 T(n)。n 自适应，避免小专业被误判成趋势。
6. 趋势标签      两段同向且均显著 → 持续升温/降温；方向相反 → 震荡；
   仅一段显著 → 单年跳变；均不显著 → 平稳。
7. 等效分        把各年门槛位次都用**最新一年**的一分一段表换算成分数再相减，
   得到「同一批考生水平下，门槛降/升了多少分」——面向用户的一线口径，
   因为超额漂移 e 的正号表示「变松」，对普通用户读起来是反的。
"""
import bisect
import math
import re
from collections import defaultdict

import numpy as np

SUBJECTS = ["物理学科类", "历史学科类"]
BATCHES = ["本科批", "专科批"]
YEARS = [2024, 2025, 2026]
STEPS = [(2024, 2025), (2025, 2026)]

MIN_UNITS = 5          # 专业层最少配对单元数，低于此判「样本不足」
CONCORD_MIN = 0.60     # 同向率门槛
PERM_DRAWS = 20000     # 置换抽样次数
PERM_ALPHA = 0.05      # 双侧显著性水平
N_GRID = [3, 5, 8, 12, 18, 25, 35, 50, 75, 110, 160, 240, 350, 500]

# 面向用户的中性事实文案（PRODUCT.md：不用「降温/好考」等带价值判断的词）
LABEL_DISPLAY = {
    "持续降温": "门槛连降两年",
    "持续升温": "门槛连升两年",
    "趋势（内部分化）": "连降两年·院校分化",
    "震荡/大小年": "大小年波动",
    "单年跳变": "近一年跳变",
    "平稳": "近三年平稳",
    "样本不足": "样本不足",
}
# 仅这三个进表格徽标；平稳/样本不足一律不渲染（house rule：数据为空不占位）
LABELS_BADGE = ("持续降温", "持续升温", "趋势（内部分化）")

BRACKETS = re.compile(r"[（(\[【].*?[)）\]】]")
_PUNCT = str.maketrans("（）［］【】，、；：·　", "()[][],,;;: ")



def name_key(name):
    """规范化招生专业名：全角标点转半角、去空格。跨年比对的稳定键。

    实测同一单元会在不同年份写成「临床医学(5+3一体化,儿科学)」与
    「临床医学(5+3一体化，儿科学)」——只差一个全角逗号。"""
    return (name or "").translate(_PUNCT).replace(" ", "")


def norm_major(name):
    """去掉括号内的方向/校区/合作办学后缀，得到聚合用的专业名（专科批口径）。"""
    return BRACKETS.sub("", name or "").strip() or (name or "").strip()


# --------------------------------------------------------------------------
# 取数
# --------------------------------------------------------------------------
def load(cur):
    """返回 (bases, rows)。bases[(year,subject)] = 该年该学科类考生基数。"""
    cur.execute("""
        SELECT year, subject, max(cumulative_rank)
          FROM score_rank WHERE category = '普通类'
         GROUP BY year, subject""")
    bases = {(y, s): float(n) for y, s, n in cur.fetchall()}

    cur.execute("""
        SELECT a.year, a.subject, a.batch, a.school_code, a.school_name,
               coalesce(a.major_code, ''), a.major_name, a.lowest_rank,
               a.lowest_score, coalesce(a.flags, '{}'),
               m.catalog_name,
               coalesce(p.is_985, false), coalesce(p.is_211, false),
               coalesce(p.is_dfc, false), coalesce(p.nature, '')
          FROM admission_scores a
          LEFT JOIN major_name_map m ON m.admission_name = a.major_name
          LEFT JOIN school_profiles p ON p.code = a.school_code
         WHERE a.category = '普通类'
           AND a.batch = ANY(%s)
           AND a.is_collection = FALSE
           AND a.score_kind = '投档最低分'
           AND a.lowest_rank IS NOT NULL
    """, (BATCHES,))

    rows = []
    for (yr, subj, batch, scode, sname, mcode, mname, rank, score,
         flags, catalog, is985, is211, isdfc, nature) in cur.fetchall():
        base = bases.get((yr, subj))
        if not base:
            continue
        rows.append({
            "year": yr, "subject": subj, "batch": batch,
            "school_code": scode, "school_name": sname,
            "major_code": mcode, "major_name": mname,
            "rank": rank, "score": float(score) if score is not None else None,
            "pct": rank / base,
            "flags": list(flags or []),
            # 本科批用标准专业目录；专科批 catalog 覆盖仅 33.6%（目录是本科的），
            # 强行套用会把高职专业错并到同名本科专业上，故改用去括号原始名。
            "major_key": (catalog if (batch == "本科批" and catalog)
                          else norm_major(mname)),
            "mapped": bool(batch == "本科批" and catalog),
            "name_key": name_key(mname),
            "tier": ("985" if is985 else "211" if is211 else "双一流" if isdfc
                     else ("民办" if nature and "民办" in nature else "普通公办")),
        })
    return bases, rows


def _index(rows, keyf):
    d = defaultdict(list)
    for i, r in enumerate(rows):
        k = keyf(r)
        if k is not None:
            d[k].append(i)
    return d


def pair_year(rows_y1, rows_y2):
    """同单元跨年配对，两趟。

    1) 先按 (院校代码, 省内专业代码, 规范化专业名) 精确配——三者齐全才配，
       用于区分同名不同代码的多个单元（如石家庄邮电「邮政快递运营管理」12 个
       定向单元，门槛横跨 6.0 万~8.2 万）；
    2) 剩余的再按 (院校代码, 规范化专业名) 配，且仅在两边各剩唯一一个时才配，
       用于覆盖「省内专业代码逐年轮换但专业未变」的情况。

    **专业代码必须与专业名同时匹配**：省内专业代码是逐年重排的顺序号，不是稳定
    标识。例如中国医科大学「临床医学」2024 年代码 09、2025 年代码 04，而 2024 年
    的代码 04 是另一个专业——只按代码配会把两个不同专业接成一条时间线。
    """
    used1, used2, out = set(), set(), []
    passes = (
        (lambda r: (r["school_code"], r["major_code"], r["name_key"])
         if r["major_code"] else None, "code+name"),
        (lambda r: (r["school_code"], r["name_key"]), "name"),
    )
    for keyf, tag in passes:
        i1, i2 = _index(rows_y1, keyf), _index(rows_y2, keyf)
        for k, a_idx in i1.items():
            b_idx = i2.get(k)
            if not b_idx:
                continue
            a_free = [i for i in a_idx if i not in used1]
            b_free = [i for i in b_idx if i not in used2]
            if len(a_free) != 1 or len(b_free) != 1:
                continue                      # 有歧义就不配，宁缺毋滥
            ia, ib = a_free[0], b_free[0]
            used1.add(ia)
            used2.add(ib)
            out.append((rows_y1[ia], rows_y2[ib], tag))
    return out


# --------------------------------------------------------------------------
# 配对 + 去大盘漂移
# --------------------------------------------------------------------------
def build_pairs(rows):
    """返回 (units, pairs, market)。units 供单元层导出，pairs 按 (学科类,批次,年段) 分组。"""
    by_grid = defaultdict(lambda: defaultdict(list))       # (subject,batch) -> year -> rows
    for r in rows:
        by_grid[(r["subject"], r["batch"])][r["year"]].append(r)

    raw = defaultdict(list)
    linked = {}                                            # id(row) -> 单元编号
    uid = 0
    for (subj, batch), yrs in by_grid.items():
        for step in STEPS:
            y1, y2 = step
            if y1 not in yrs or y2 not in yrs:
                continue
            for a, b, how in pair_year(yrs[y1], yrs[y2]):
                raw[(subj, batch, step)].append({
                    "a": a, "b": b, "how": how,
                    "delta": math.log(b["pct"] / a["pct"]),
                    "ratio_rank": b["rank"] / a["rank"],
                })
                ka, kb = id(a), id(b)
                u = linked.get(ka) or linked.get(kb)
                if u is None:
                    uid += 1
                    u = uid
                linked[ka] = linked[kb] = u

    for r in rows:
        r["uid"] = linked.get(id(r))

    pairs, market = {}, {}
    for k, lst in raw.items():
        m = float(np.median([p["delta"] for p in lst]))
        market[k] = m
        for p in lst:
            p["e"] = p["delta"] - m
        pairs[k] = lst

    units = defaultdict(dict)
    for r in rows:
        if r["uid"]:
            units[r["uid"]][r["year"]] = r
        else:
            uid += 1
            units[uid][r["year"]] = r                       # 从未配上的单年单元
    return units, pairs, market


# --------------------------------------------------------------------------
# 置换阈值 T(n)
# --------------------------------------------------------------------------
def perm_thresholds(e_values, rng):
    """对给定 e 池，返回 {n: T(n)}：随机 n 元子集中位数的双侧 95% 临界值。"""
    arr = np.asarray(e_values, dtype=float)
    M = len(arr)
    out = {}
    for n in N_GRID:
        if n > M:
            break
        idx = rng.integers(0, M, size=(PERM_DRAWS, n))   # 有放回，M 远大于 n
        med = np.median(arr[idx], axis=1)
        lo = np.quantile(med, PERM_ALPHA / 2)
        hi = np.quantile(med, 1 - PERM_ALPHA / 2)
        out[n] = float(max(abs(lo), abs(hi)))
    return out


def threshold_at(table, n):
    """在 T(n) 网格上按 log(n) 线性插值；超出网格取端点。"""
    ns = sorted(table)
    if not ns:
        return float("inf")
    if n <= ns[0]:
        return table[ns[0]]
    if n >= ns[-1]:
        return table[ns[-1]]
    for i in range(len(ns) - 1):
        a, b = ns[i], ns[i + 1]
        if a <= n <= b:
            w = (math.log(n) - math.log(a)) / (math.log(b) - math.log(a))
            return table[a] + w * (table[b] - table[a])
    return table[ns[-1]]


# --------------------------------------------------------------------------
# 专业层聚合
# --------------------------------------------------------------------------
def aggregate(pairs, thr, shuffle_rng=None):
    """按 (学科类, 批次, 专业) × 年段 聚合；shuffle_rng 非空时打乱专业标签做安慰剂检验。"""
    agg = defaultdict(dict)
    for (subj, batch, step), lst in pairs.items():
        keys = [p["a"]["major_key"] for p in lst]
        if shuffle_rng is not None:
            keys = list(keys)
            shuffle_rng.shuffle(keys)
        buckets = defaultdict(list)
        for p, mk in zip(lst, keys):
            buckets[mk].append(p)
        for mk, ps in buckets.items():
            es = np.array([p["e"] for p in ps], dtype=float)
            E = float(np.median(es))
            n = len(es)
            concord = float(np.mean(np.sign(es) == np.sign(E))) if E else 0.0
            T = threshold_at(thr[(subj, batch, step)], n)
            agg[(subj, batch, mk)][step] = {
                "n": n, "E": E, "T": T, "sig": abs(E) > T,
                "concord": concord,
                "E_rank": float(np.median([math.log(p["ratio_rank"]) for p in ps])),
                "pairs": ps,
            }
    return agg


def label(a, b):
    """a=2024→2025 段，b=2025→2026 段。e>0 表示门槛百分位变大 = 变松 = 降温。"""
    if a is None or b is None:
        return "样本不足", "缺一个年段的配对数据"
    if a["n"] < MIN_UNITS or b["n"] < MIN_UNITS:
        return "样本不足", f"配对单元数不足（{a['n']} / {b['n']}，门槛 {MIN_UNITS}）"
    same_dir = a["E"] * b["E"] > 0
    both_sig = a["sig"] and b["sig"]
    conc_ok = a["concord"] >= CONCORD_MIN and b["concord"] >= CONCORD_MIN
    if both_sig and same_dir and conc_ok:
        return ("持续降温" if a["E"] > 0 else "持续升温"), "两段同向且均超置换阈值，单元同向率达标"
    if both_sig and same_dir and not conc_ok:
        return "趋势（内部分化）", "两段同向且显著，但单元同向率偏低，由部分院校拉动"
    if both_sig and not same_dir:
        return "震荡/大小年", "两段均显著但方向相反"
    if a["sig"] != b["sig"]:
        seg = "2024→2025" if a["sig"] else "2025→2026"
        return "单年跳变", f"仅 {seg} 显著，另一段落在噪声带内"
    return "平稳", "两段均未超过置换阈值"


# --------------------------------------------------------------------------
# 混杂因素：供给（单元数）与院校层次分化
# --------------------------------------------------------------------------
def supply_table(rows):
    """supply[(subject,batch,major_key)][year] = 该年该专业的招生单元数（招生计划的代理）。"""
    sup = defaultdict(lambda: defaultdict(int))
    for r in rows:
        sup[(r["subject"], r["batch"], r["major_key"])][r["year"]] += 1
    return sup


def tier_breakdown(ps):
    """按院校层次拆超额漂移，用于识别「头部塌、基层稳」这类内部分化。"""
    by = defaultdict(list)
    for p in ps:
        by[p["a"]["tier"]].append(p["e"])
    return {t: (len(v), float(np.median(v))) for t, v in sorted(by.items())}


# --------------------------------------------------------------------------
# 等效分：面向用户的一线口径
# --------------------------------------------------------------------------
def load_score_tables(cur):
    """返回 tbl[(year, subject)] = (累计位次升序, 对应分数)，供位次↔分数换算。"""
    cur.execute("""SELECT year, subject, score, cumulative_rank
                     FROM score_rank WHERE category = '普通类'
                    ORDER BY subject, year, cumulative_rank""")
    tbl = defaultdict(lambda: ([], []))
    for y, s, sc, cr in cur.fetchall():
        ranks, scores = tbl[(y, s)]
        ranks.append(cr)
        scores.append(float(sc))
    return dict(tbl)


def rank_to_score(tbl, year, subject, rank):
    """用指定年份的一分一段表把位次换算成分数（取第一个累计位次 >= rank 的档）。"""
    pair = tbl.get((year, subject))
    if not pair or not pair[0]:
        return None
    ranks, scores = pair
    return scores[min(bisect.bisect_left(ranks, rank), len(scores) - 1)]


def equivalent_scores(units, tbl, y_from=None, y_to=None):
    """等效分变化：把 y_from 与 y_to 的门槛位次都换算到 **y_to 的分数尺**再相减。

    负值 = 同一批考生水平下，门槛降了多少分（更好考）；正值 = 涨了多少分。
    这是给用户看的一线数字——超额漂移 e 的正号表示「变松」，方向与直觉相反。

    返回 (per_major, market)：
      per_major[(subject, batch, major_key)] = 该专业各单元等效分变化的中位数
      market[(subject, batch)]               = 同期全省大盘的中位数（必须与专业值并列展示，
                                               否则用户会把大盘漂移误读成该专业自身的变化）
    """
    y_from = y_from if y_from is not None else YEARS[0]
    y_to = y_to if y_to is not None else YEARS[-1]
    per, mkt = defaultdict(list), defaultdict(list)
    for yrs in units.values():
        a, b = yrs.get(y_from), yrs.get(y_to)
        if a is None or b is None or not a["rank"] or not b["rank"]:
            continue
        s_from = rank_to_score(tbl, y_to, a["subject"], a["rank"])
        s_to = rank_to_score(tbl, y_to, b["subject"], b["rank"])
        if s_from is None or s_to is None:
            continue
        d = s_to - s_from
        per[(a["subject"], a["batch"], a["major_key"])].append(d)
        mkt[(a["subject"], a["batch"])].append(d)
    return ({k: float(np.median(v)) for k, v in per.items()},
            {k: float(np.median(v)) for k, v in mkt.items()})
