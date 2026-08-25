#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""专业冷热趋势分析（2024–2026）——只读研究/诊断脚本，不写库、不改产品代码。

计算内核在 `etl/major_trend_core.py`，与入库 ETL（`etl/load_major_trend.py`）共用
同一份实现，保证「研究口径」与「线上口径」不会漂移。方法说明见该模块与
docs/major-trend-2024-2026.md。

用法
----
    python3 webapp/scripts/major_trend.py                # 全量，写 docs/data/*.csv
    python3 webapp/scripts/major_trend.py --check        # 口径自检（考生基数/比值分布/大盘漂移）
    python3 webapp/scripts/major_trend.py --placebo      # 假阳性自检（打乱专业标签重跑）
    python3 webapp/scripts/major_trend.py --backtest     # 锚点对比回测（2024+2025 → 2026）
"""
import argparse
import csv
import math
import os
import sys
from collections import defaultdict

import numpy as np
import psycopg2

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV = os.path.join(REPO, "webapp", "backend", ".env")
sys.path.insert(0, os.path.join(REPO, "etl"))

from major_trend_core import (                                    # noqa: E402
    SUBJECTS, BATCHES, YEARS, STEPS,
    MIN_UNITS, CONCORD_MIN, PERM_DRAWS, PERM_ALPHA, N_GRID,
    name_key, norm_major, load, _index, pair_year, build_pairs,
    perm_thresholds, threshold_at, aggregate, label,
    supply_table, tier_breakdown,
)


def dsn():
    """只读连接串：优先 .env 的 gaokao_web_ro，任何写操作会被数据库直接拒绝。"""
    if os.path.exists(ENV):
        for line in open(ENV, encoding="utf-8"):
            if line.startswith("GAOKAO_DSN="):
                return line.split("=", 1)[1].strip()
    return os.environ["GAOKAO_DSN"]


# --------------------------------------------------------------------------
# 自检
# --------------------------------------------------------------------------
def run_check(pairs, market, bases):
    print("=" * 74)
    print("口径自检 A：考生基数（score_rank 普通类最大累计位次）")
    print("=" * 74)
    for s in SUBJECTS:
        line = [f"{s}:"]
        prev = None
        for y in YEARS:
            n = bases.get((y, s))
            chg = f" ({(n/prev-1)*100:+.1f}%)" if prev else ""
            line.append(f"{y}={int(n):,}{chg}")
            prev = n
        print("  " + "  ".join(line))

    print()
    print("=" * 74)
    print("口径自检 B：全局门槛年际比值分布（原始位次口径，对齐 backtest_report.txt）")
    print("=" * 74)
    print(f"{'学科类':<12}{'批次':<8}{'年段':<14}{'配对数':>7}"
          f"{'P10':>7}{'P25':>7}{'P50':>7}{'P75':>7}{'P90':>7}")
    for subj in SUBJECTS:
        for batch in BATCHES:
            for step in STEPS:
                lst = pairs.get((subj, batch, step))
                if not lst:
                    continue
                r = np.array([p["ratio_rank"] for p in lst])
                q = np.quantile(r, [.10, .25, .50, .75, .90])
                print(f"{subj:<12}{batch:<8}{step[0]}→{step[1]:<9}{len(lst):>7}"
                      + "".join(f"{v:>7.2f}" for v in q))

    print()
    print("=" * 74)
    print("口径自检 C：大盘漂移基准 m（百分位对数口径）与其原始位次等价倍数")
    print("=" * 74)
    for subj in SUBJECTS:
        for batch in BATCHES:
            for step in STEPS:
                k = (subj, batch, step)
                if k not in market:
                    continue
                m = market[k]
                print(f"  {subj} {batch} {step[0]}→{step[1]}: "
                      f"m={m:+.4f}（百分位中位变动 {math.exp(m)-1:+.1%}）")


def run_placebo(pairs, thr, seed=7):
    rng = np.random.default_rng(seed)
    agg = aggregate(pairs, thr, shuffle_rng=rng)
    counts = defaultdict(int)
    for (subj, batch, mk), steps in agg.items():
        lab, _ = label(steps.get(STEPS[0]), steps.get(STEPS[1]))
        counts[lab] += 1
    total = sum(v for k, v in counts.items() if k != "样本不足")
    trend = counts["持续降温"] + counts["持续升温"] + counts["趋势（内部分化）"]
    print("=" * 74)
    print("安慰剂自检：打乱专业标签后重跑（期望「持续趋势」回落到 ~5% 假阳性水平）")
    print("=" * 74)
    for k, v in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"  {k:<16}{v:>5}")
    if total:
        print(f"\n  可判定专业 {total} 个，其中被判持续趋势 {trend} 个 "
              f"= {trend/total:.1%}（应接近 5%）")


# --------------------------------------------------------------------------
# 输出
# --------------------------------------------------------------------------
def write_major_csv(path, agg, sup, thr):
    cols = ["学科类", "批次", "专业", "标签", "判定依据",
            "配对数_24_25", "超额漂移_24_25", "阈值_24_25", "显著_24_25", "同向率_24_25",
            "配对数_25_26", "超额漂移_25_26", "阈值_25_26", "显著_25_26", "同向率_25_26",
            "两段合计超额漂移", "原始位次口径_24_25", "原始位次口径_25_26",
            "单元数_2024", "单元数_2025", "单元数_2026", "供给变动_24_26",
            "层次分化_25_26"]
    out = []
    for (subj, batch, mk), steps in agg.items():
        a, b = steps.get(STEPS[0]), steps.get(STEPS[1])
        lab, why = label(a, b)
        s = sup[(subj, batch, mk)]
        n24, n25, n26 = s.get(2024, 0), s.get(2025, 0), s.get(2026, 0)
        tiers = tier_breakdown(b["pairs"]) if b else {}
        tier_txt = " ".join(f"{t}:{n}个/{v:+.1%}" for t, (n, v) in tiers.items())
        out.append([
            subj, batch, mk, lab, why,
            a["n"] if a else "", f"{a['E']:+.4f}" if a else "",
            f"{a['T']:.4f}" if a else "", ("是" if a and a["sig"] else "否") if a else "",
            f"{a['concord']:.2f}" if a else "",
            b["n"] if b else "", f"{b['E']:+.4f}" if b else "",
            f"{b['T']:.4f}" if b else "", ("是" if b and b["sig"] else "否") if b else "",
            f"{b['concord']:.2f}" if b else "",
            f"{(a['E'] + b['E']):+.4f}" if a and b else "",
            f"{a['E_rank']:+.4f}" if a else "", f"{b['E_rank']:+.4f}" if b else "",
            n24, n25, n26, f"{(n26 - n24):+d}",
            tier_txt,
        ])
    # 排序：先按标签重要性，再按两段合计超额漂移绝对值降序
    order = {"持续降温": 0, "持续升温": 1, "趋势（内部分化）": 2, "单年跳变": 3,
             "震荡/大小年": 4, "平稳": 5, "样本不足": 6}
    def keyf(r):
        try:
            mag = -abs(float(r[15]))
        except ValueError:
            mag = 0
        return (order.get(r[3], 9), r[0], r[1], mag)
    out.sort(key=keyf)
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(out)
    return out


def write_unit_csv(path, by_unit, pairs, agg):
    lab_of = {}
    for (subj, batch, mk), steps in agg.items():
        lab_of[(subj, batch, mk)] = label(steps.get(STEPS[0]), steps.get(STEPS[1]))[0]
    cols = ["学科类", "批次", "院校代码", "院校名称", "专业代码", "招生专业名",
            "归一专业", "院校层次", "标记",
            "位次_2024", "位次_2025", "位次_2026",
            "分数_2024", "分数_2025", "分数_2026",
            "百分位_2024", "百分位_2025", "百分位_2026",
            "超额漂移_24_25", "超额漂移_25_26", "专业标签"]
    e_map = defaultdict(dict)
    for (subj, batch, step), lst in pairs.items():
        for p in lst:
            e_map[p["a"]["uid"]][step] = p["e"]
    rows = []
    for uk, yrs in by_unit.items():
        any_r = yrs.get(max(yrs))
        mk = any_r["major_key"]
        e = e_map.get(uk, {})
        rows.append([
            any_r["subject"], any_r["batch"], any_r["school_code"], any_r["school_name"],
            any_r["major_code"], any_r["major_name"], mk, any_r["tier"],
            "|".join(any_r["flags"]),
            *[yrs[y]["rank"] if y in yrs else "" for y in YEARS],
            *[yrs[y]["score"] if y in yrs else "" for y in YEARS],
            *[f"{yrs[y]['pct']:.5f}" if y in yrs else "" for y in YEARS],
            f"{e[STEPS[0]]:+.4f}" if STEPS[0] in e else "",
            f"{e[STEPS[1]]:+.4f}" if STEPS[1] in e else "",
            lab_of.get((any_r["subject"], any_r["batch"], mk), ""),
        ])
    rows.sort(key=lambda r: (r[0], r[1], r[6], r[3]))
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(cols)
        w.writerows(rows)
    return rows


def print_thresholds(thr):
    print("=" * 74)
    print("置换阈值 T(n)：超额漂移中位数需超过该值才算显著（双侧 95%）")
    print("=" * 74)
    shown = [5, 12, 25, 50, 110, 240]
    print(f"{'学科类':<12}{'批次':<8}{'年段':<13}" + "".join(f"{'n='+str(n):>10}" for n in shown))
    for subj in SUBJECTS:
        for batch in BATCHES:
            for step in STEPS:
                t = thr.get((subj, batch, step))
                if not t:
                    continue
                cells = []
                for n in shown:
                    v = threshold_at(t, n) if n <= max(t) else None
                    cells.append(f"{math.exp(v)-1:>9.1%}" if v else f"{'-':>10}")
                print(f"{subj:<12}{batch:<8}{step[0]}→{step[1]:<8}" + "".join(f"{c:>10}" for c in cells))
    print("\n  （单位已折算回「门槛百分位相对全省大盘的变动幅度」；n 越大阈值越低）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="只跑口径自检")
    ap.add_argument("--placebo", action="store_true", help="只跑安慰剂假阳性自检")
    ap.add_argument("--backtest", action="store_true", help="只跑使用价值回测（2024+2025 → 2026）")
    ap.add_argument("--out", default=os.path.join(REPO, "docs", "data"))
    ap.add_argument("--seed", type=int, default=20260825)
    args = ap.parse_args()

    conn = psycopg2.connect(dsn())
    conn.set_session(readonly=True)
    cur = conn.cursor()
    bases, rows = load(cur)
    conn.close()

    by_unit, pairs, market = build_pairs(rows)

    if args.check:
        run_check(pairs, market, bases)
        return

    rng = np.random.default_rng(args.seed)
    thr = {k: perm_thresholds([p["e"] for p in lst], rng) for k, lst in pairs.items()}

    if args.placebo:
        run_placebo(pairs, thr)
        return

    if args.backtest:
        run_backtest(rows, pairs, thr)
        return

    print_thresholds(thr)
    print()

    agg = aggregate(pairs, thr)
    sup = supply_table(rows)

    os.makedirs(args.out, exist_ok=True)
    mpath = os.path.join(args.out, "major-trend-major.csv")
    upath = os.path.join(args.out, "major-trend-unit.csv")
    mout = write_major_csv(mpath, agg, sup, thr)
    uout = write_unit_csv(upath, by_unit, pairs, agg)

    counts = defaultdict(int)
    for r in mout:
        counts[(r[1], r[3])] += 1
    print("=" * 74)
    print("趋势标签分布")
    print("=" * 74)
    labs = ["持续降温", "持续升温", "趋势（内部分化）", "单年跳变", "震荡/大小年", "平稳", "样本不足"]
    print(f"{'批次':<10}" + "".join(f"{l:>12}" for l in labs))
    for batch in BATCHES:
        print(f"{batch:<10}" + "".join(f"{counts[(batch, l)]:>12}" for l in labs))

    print(f"\n专业层 {len(mout)} 行 → {mpath}")
    print(f"单元层 {len(uout)} 行 → {upath}")




# --------------------------------------------------------------------------
# 使用价值回测：只用 2024+2025 预测 2026，比较三种锚点
# --------------------------------------------------------------------------
def run_backtest(rows, pairs, thr):
    """模拟「手上只有两年数据」的真实处境，检验趋势调整是否真的预测更准。

    三种锚点：
      A 现行区间中位 median(r24, r25)  —— match.py 的稳/冲分界
      B 最近一年     r25              —— 朴素「以去年为准」
      C 趋势调整     r25 × exp(δ̂)     —— δ̂ = 该专业 2024→2025 的中位总漂移
                                        （含大盘，因为预测下一年门槛要连大盘一起外推）
    真值 = 2026 实际门槛 r26。指标 = |ln(预测/真实)| 的中位数（越小越准）。
    """
    step1 = STEPS[0]
    # 该专业 2024→2025 的中位总漂移 δ（不去大盘：预测绝对门槛需要连大盘一起外推）
    drift, market1 = defaultdict(list), {}
    for (subj, batch, step), lst in pairs.items():
        if step != step1:
            continue
        market1[(subj, batch)] = float(np.median([p["delta"] for p in lst]))
        for p in lst:
            drift[(subj, batch, p["a"]["major_key"])].append(p["delta"])
    dhat = {k: float(np.median(v)) for k, v in drift.items() if len(v) >= MIN_UNITS}

    # 用「仅 2024→2025 一段」重判趋势（真实预测场景只有这一段可用）
    sig1 = {}
    for (subj, batch, step), lst in pairs.items():
        if step != step1:
            continue
        b = defaultdict(list)
        for p in lst:
            b[p["a"]["major_key"]].append(p["e"])
        for mk, es in b.items():
            if len(es) < MIN_UNITS:
                continue
            E = float(np.median(es))
            sig1[(subj, batch, mk)] = abs(E) > threshold_at(thr[(subj, batch, step1)], len(es))

    by_grid = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_grid[(r["subject"], r["batch"])][r["year"]].append(r)

    res = defaultdict(lambda: defaultdict(list))
    for (subj, batch), yrs in by_grid.items():
        if not all(y in yrs for y in YEARS):
            continue
        p12 = {id(a): b for a, b, _ in pair_year(yrs[2024], yrs[2025])}
        p23 = {id(b): c for b, c, _ in pair_year(yrs[2025], yrs[2026])}
        for a in yrs[2024]:
            b = p12.get(id(a))
            if b is None:
                continue
            c = p23.get(id(b))
            if c is None:
                continue
            mk = a["major_key"]
            d = dhat.get((subj, batch, mk))
            if d is None:
                continue
            grp = "趋势专业" if sig1.get((subj, batch, mk)) else "非趋势专业"
            r24, r25, r26 = a["rank"], b["rank"], c["rank"]
            preds = {
                "A 区间中位(现行)": (r24 + r25) / 2,
                "B 最近一年": r25,
                "C 趋势调整": r25 * math.exp(d),
            }
            for name, pr in preds.items():
                for g in (grp, "全部"):
                    res[(subj, batch, g)][name].append(abs(math.log(pr / r26)))

    print("=" * 88)
    print("使用价值回测：只用 2024+2025 预测 2026 实际门槛，|ln(预测/真实)| 中位数（越小越准）")
    print("=" * 88)
    print(f"{'学科类':<12}{'批次':<8}{'分组':<12}{'单元数':>7}"
          f"{'A 区间中位':>12}{'B 最近一年':>12}{'C 趋势调整':>12}{'C 相对 A':>11}")
    for (subj, batch, g), d in sorted(res.items()):
        n = len(d["A 区间中位(现行)"])
        a = float(np.median(d["A 区间中位(现行)"]))
        b = float(np.median(d["B 最近一年"]))
        c = float(np.median(d["C 趋势调整"]))
        print(f"{subj:<12}{batch:<8}{g:<12}{n:>7}"
              f"{a:>12.4f}{b:>12.4f}{c:>12.4f}{(c/a-1):>+10.1%}")

    print()
    print("=" * 88)
    print("保档安全线检验：被现行规则判「保」的单元，2026 实际门槛是否仍在安全线外")
    print("（安全线 = min(r24,r25) × 0.85；口径同 backtest_report.txt）")
    print("=" * 88)
    print(f"{'学科类':<12}{'批次':<8}{'分组':<12}{'单元数':>7}{'仍成立':>9}")
    hold = defaultdict(lambda: [0, 0])
    for (subj, batch), yrs in by_grid.items():
        if not all(y in yrs for y in YEARS):
            continue
        p12 = {id(a): b for a, b, _ in pair_year(yrs[2024], yrs[2025])}
        p23 = {id(b): c for b, c, _ in pair_year(yrs[2025], yrs[2026])}
        for a in yrs[2024]:
            b = p12.get(id(a))
            c = p23.get(id(b)) if b is not None else None
            if c is None:
                continue
            mk = a["major_key"]
            if (subj, batch, mk) not in sig1:
                continue
            grp = "趋势专业" if sig1[(subj, batch, mk)] else "非趋势专业"
            safe = min(a["rank"], b["rank"]) * MATCH_MARGIN
            for g in (grp, "全部"):
                hold[(subj, batch, g)][1] += 1
                if c["rank"] >= safe:
                    hold[(subj, batch, g)][0] += 1
    for (subj, batch, g), (ok, tot) in sorted(hold.items()):
        print(f"{subj:<12}{batch:<8}{g:<12}{tot:>7}{ok/tot:>8.1%}")


MATCH_MARGIN = 0.85          # 与 app/services/match.py MATCH_CONFIG['safe_margin'] 一致


if __name__ == "__main__":
    main()
