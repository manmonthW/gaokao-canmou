#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_xk.py —— 选科匹配分层审计（规划第一步，只读）。

对照 2027 官方选科表与 admission_scores（2025/2026）投档单元，
逐层统计匹配命中率并输出残差清单，为归一化方案与院校别名表提供依据：
  L0 精确匹配 (school_name, major_name)
  L1 格式归一化（去空白、全角/半角统一）
  L2 基础名匹配（两侧剥掉括号后缀）
  L4 院校级兜底（官方表中专业名为空的行 / 学校是否在表）

用法：
  cd /home/ekewang/projects/gaokao/ln && python3 etl/audit_xk.py
输出：stdout 摘要 + etl/data/audit_xk_residual.md 残差明细
"""
import difflib
import os
import re
from collections import Counter, defaultdict

import psycopg2

from config import DSN

YEAR = 2027
POOL_YEARS = (2025, 2026)
OUT = os.path.join(os.path.dirname(__file__), "data", "audit_xk_residual.md")

FULL2HALF = {"（": "(", "）": ")", "，": ",", "、": ",", "　": "", " ": ""}
_PAREN = re.compile(r"\([^()]*\)")


def norm1(s):
    """L1 格式归一化：去空白、全角括号/逗号统一为半角。"""
    if not s:
        return ""
    t = str(s).strip()
    for a, b in FULL2HALF.items():
        t = t.replace(a, b)
    return t


def base_name(s):
    """L2 基础名：norm1 之后反复剥掉括号组（兼容嵌套）。"""
    t = norm1(s)
    while True:
        t2 = _PAREN.sub("", t).strip(" -,，、")
        if t2 == t:
            return t2
        t = t2


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # ---------- 官方选科表（2027 三表合并库） ----------
    cur.execute(
        """SELECT school_code, school_name, major_name, first_req, re_req, raw_text
           FROM subject_requirements WHERE year=%s""", (YEAR,))
    off_rows = cur.fetchall()

    off_raw, off_n1, off_base = {}, {}, {}
    off_school_empty = defaultdict(set)   # 院校级行（专业名为空）
    off_schools = set()
    off_paren = 0
    req_text_stats = Counter()
    for sc, sn, mn, fr, rr, raw in off_rows:
        sn1 = norm1(sn)
        off_schools.add(sn1)
        pair = (fr, rr)
        req_text_stats[pair] += 1
        if mn:
            off_raw.setdefault((sn, mn), set()).add(pair)
            off_n1.setdefault((sn1, norm1(mn)), set()).add(pair)
            off_base.setdefault((sn1, base_name(mn)), set()).add(pair)
            if "(" in norm1(mn):
                off_paren += 1
        else:
            off_school_empty[sn1].add(pair)

    # ---------- 投档单元池（2025/2026，匹配池口径） ----------
    cur.execute(
        """SELECT DISTINCT school_name, major_name FROM admission_scores
           WHERE year IN %s""", (POOL_YEARS,))
    units = cur.fetchall()
    cur.execute(
        """SELECT batch, count(*) FROM admission_scores
           WHERE year IN %s GROUP BY batch ORDER BY 2 DESC""", (POOL_YEARS,))
    batch_dist = cur.fetchall()
    cur.execute(
        """SELECT DISTINCT school_name FROM admission_scores
           WHERE year IN %s""", (POOL_YEARS,))
    adm_schools = {r[0] for r in cur.fetchall()}
    conn.close()

    adm_paren = sum(1 for _, m in units if m and "(" in norm1(m))

    # ---------- 逐单元分层归类 ----------
    hits = Counter()
    l2_ambiguous = 0
    l2_amb_samples = []
    residual_by_school = defaultdict(list)
    school_hit = defaultdict(lambda: False)
    for sn, mn in units:
        sn1 = norm1(sn)
        if (sn, mn) in off_raw:
            hits["L0"] += 1; school_hit[sn] = True; continue
        if (sn1, norm1(mn)) in off_n1:
            hits["L1"] += 1; school_hit[sn] = True; continue
        k2 = (sn1, base_name(mn))
        if k2 in off_base:
            hits["L2"] += 1; school_hit[sn] = True
            if len(off_base[k2]) > 1:
                l2_ambiguous += 1
                if len(l2_amb_samples) < 25:
                    l2_amb_samples.append((sn, mn, sorted(off_base[k2])))
            continue
        if sn1 in off_school_empty:
            hits["L4_院校级行"] += 1; school_hit[sn] = True; continue
        if sn1 in off_schools:
            hits["L4b_专业未收录"] += 1; school_hit[sn] = True
        else:
            hits["L4c_院校未收录"] += 1
        residual_by_school[sn].append(mn)

    total = len(units)
    matched = hits["L0"] + hits["L1"] + hits["L2"] + hits["L4_院校级行"]

    # ---------- 院校级残差与别名候选 ----------
    zero_hit_schools = sorted(s for s in adm_schools if not school_hit[s])
    off_school_list = sorted(off_schools)
    alias_cand = []
    for s in zero_hit_schools:
        sug = difflib.get_close_matches(norm1(s), off_school_list, n=3, cutoff=0.6)
        alias_cand.append((s, sug))
    official_only = sorted(off_schools - {norm1(s) for s in adm_schools})

    # ---------- stdout 摘要 ----------
    print("== 官方 2027 选科表 ==")
    print(f"总行数 {len(off_rows)} | 院校数 {len(off_schools)} | "
          f"专业名带括号行 {off_paren} | "
          f"院校级空专业行 {sum(len(v) for v in off_school_empty.values())}")
    print("要求值分布 Top8:")
    for (fr, rr), n in req_text_stats.most_common(8):
        print(f"  {n:>6}  首选={fr} 再选={rr}")
    print(f"\n== 投档单元池（{POOL_YEARS}）==")
    print(f"distinct 单元 {total} | distinct 学校 {len(adm_schools)} | "
          f"专业名带括号 {adm_paren}")
    print("批次分布:", batch_dist)
    print("\n== 分层命中 ==")
    for k in ["L0", "L1", "L2", "L4_院校级行", "L4b_专业未收录", "L4c_院校未收录"]:
        n = hits[k]
        print(f"  {k:<14} {n:>6}  ({n / total:.1%})")
    print(f"专业级匹配合计 {matched} ({matched / total:.1%})；"
          f"其中 L2 歧义键（多要求）{l2_ambiguous}")
    if l2_amb_samples:
        print("L2 歧义样例:")
        for sn, mn, pairs in l2_amb_samples[:8]:
            print(f"  {sn} | {mn} -> {pairs}")
    print(f"\n== 院校覆盖 ==")
    print(f"投档库学校 {len(adm_schools)} | 至少 1 单元命中 {sum(school_hit.values())} | "
          f"零命中 {len(zero_hit_schools)} | 官方表独有(2027新设/军校等) {len(official_only)}")
    print("\n== 残差 Top15（L2 后仍未匹配单元最多的学校）==")
    for sn, mns in sorted(residual_by_school.items(), key=lambda kv: -len(kv[1]))[:15]:
        in_off = norm1(sn) in off_schools
        print(f"  {sn}: {len(mns)} 个 {'[学校在表]' if in_off else '[学校不在表]'} "
              f"样例={mns[:3]}")

    # ---------- 明细落盘 ----------
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        f.write(f"# 选科匹配审计残差明细（{YEAR} 官方表 vs {POOL_YEARS} 投档池）\n\n")
        f.write(f"## 一、零命中学校（别名表候选，{len(alias_cand)} 所）\n\n")
        f.write("| 投档库学校名 | 官方表近似名（cutoff=0.6） |\n|---|---|\n")
        for s, sug in alias_cand:
            f.write(f"| {s} | {'、'.join(sug) if sug else '—'} |\n")
        f.write(f"\n## 二、官方表独有学校（2027 新设 / 军校 / 专科-only，"
                f"{len(official_only)} 所）\n\n")
        for s in official_only:
            f.write(f"- {s}\n")
        f.write("\n## 三、专业级残差明细（按学校）\n\n")
        for sn, mns in sorted(residual_by_school.items(), key=lambda kv: -len(kv[1])):
            in_off = norm1(sn) in off_schools
            f.write(f"### {sn}（{len(mns)} 个，{'学校在表' if in_off else '学校不在表'}）\n\n")
            for m in mns:
                f.write(f"- {m}\n")
            f.write("\n")
    print(f"\n明细已写入 {OUT}")


if __name__ == "__main__":
    main()
