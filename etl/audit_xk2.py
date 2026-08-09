#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""audit_xk2.py —— 第二轮增强审计（只读）：
1. base_name 扩展：同时剥离 [...] 方括号组（北交大式大类枚举）；
2. L3 枚举反查：从残差单元的括号/方括号内提取专业 token，
   反查该校官方专业，统计可挽回量与要求一致性；
3. 残差 Top 学校的官方专业名抽样（人眼看命名模式）；
4. 专项/民族班剥离再查；
5. admission 脏数据：school_name 含专业名的行。
"""
import re
from collections import Counter, defaultdict

import psycopg2

from config import DSN

YEAR = 2027
POOL_YEARS = (2025, 2026)

FULL2HALF = {"（": "(", "）": ")", "，": ",", "、": ",", "【": "[", "】": "]",
             "　": "", " ": ""}
_PAREN = re.compile(r"\([^()]*\)|\[[^\[\]]*\]")
_TOKEN_SPLIT = re.compile(r"[、,;；]+")
_SKIP = ("班", "计划", "民族", "合作", "学位", "师范", "定向", "学院",
         "校区", "办学", "项目", "委托", "订单", "培优", "领军", "卓越")


def norm1(s):
    if not s:
        return ""
    t = str(s).strip()
    for a, b in FULL2HALF.items():
        t = t.replace(a, b)
    return t


def base_name(s):
    t = norm1(s)
    while True:
        t2 = _PAREN.sub("", t).strip(" -,，、")
        if t2 == t:
            return t2
        t = t2


def groups_of(s):
    """提取所有 (...) 与 [...] 组的内容。"""
    return re.findall(r"\(([^()]*)\)|\[([^\[\]]*)\]", norm1(s))


def enum_tokens(s):
    """从括号/方括号组内提取候选专业 token（过滤非专业词）。"""
    toks = []
    for a, b in groups_of(s):
        for g in (a, b):
            if not g:
                continue
            for t in _TOKEN_SPLIT.split(g):
                t = base_name(t)  # token 内可能还套括号
                if len(t) < 3 or any(k in t for k in _SKIP):
                    continue
                toks.append(t)
    return toks


def _srt(pairs):
    return sorted(pairs, key=lambda p: (str(p[0]), str(p[1])))


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("""SELECT school_name, major_name, first_req, re_req
                   FROM subject_requirements WHERE year=%s""", (YEAR,))
    off_rows = cur.fetchall()
    cur.execute("""SELECT DISTINCT school_name, major_name FROM admission_scores
                   WHERE year IN %s""", (POOL_YEARS,))
    units = cur.fetchall()
    conn.close()

    off_raw, off_base = {}, {}
    off_by_school_base = defaultdict(dict)   # school -> {base: set(pairs)}
    off_by_school_raw = defaultdict(dict)    # school -> {raw: pair}
    off_schools = set()
    for sn, mn, fr, rr in off_rows:
        sn1 = norm1(sn)
        off_schools.add(sn1)
        if not mn:
            continue
        pair = (fr, rr)
        off_raw.setdefault((sn, mn), set()).add(pair)
        b = base_name(mn)
        off_base.setdefault((sn1, b), set()).add(pair)
        off_by_school_base[sn1].setdefault(b, set()).add(pair)
        off_by_school_raw[sn1][norm1(mn)] = pair

    # ---- 分层（含扩展 base：剥方括号）----
    hits = Counter()
    residual = []
    for sn, mn in units:
        sn1 = norm1(sn)
        if (sn, mn) in off_raw:
            hits["L0"] += 1; continue
        k2 = (sn1, base_name(mn))
        if k2 in off_base:
            hits["L2ext"] += 1; continue
        residual.append((sn, mn))
    total = len(units)
    print(f"总单元 {total}")
    print(f"L0 {hits['L0']} ({hits['L0']/total:.1%}) | "
          f"L2ext(剥圆括号+方括号) {hits['L2ext']} ({hits['L2ext']/total:.1%}) | "
          f"残差 {len(residual)} ({len(residual)/total:.1%})")

    # ---- L3 枚举反查 ----
    l3_ok, l3_conflict, l3_none = 0, 0, 0
    l3_conflict_samples, l3_ok_samples = [], []
    still = []
    for sn, mn in residual:
        sn1 = norm1(sn)
        pairs = set()
        for tok in enum_tokens(mn):
            sb = off_by_school_base.get(sn1, {})
            sr = off_by_school_raw.get(sn1, {})
            if tok in sb:
                pairs |= sb[tok]
            elif tok in sr:
                pairs.add(sr[tok])
        if pairs:
            if len(pairs) == 1:
                l3_ok += 1
                if len(l3_ok_samples) < 10:
                    l3_ok_samples.append((sn, mn, _srt(pairs)))
            else:
                l3_conflict += 1
                if len(l3_conflict_samples) < 15:
                    l3_conflict_samples.append((sn, mn, _srt(pairs)))
        else:
            l3_none += 1
            still.append((sn, mn))
    print(f"\nL3 枚举反查：一致 {l3_ok} | 多要求 {l3_conflict} | 无 {l3_none}")
    print("L3 一致样例:")
    for sn, mn, p in l3_ok_samples:
        print(f"  {sn} | {mn} -> {p}")
    print("L3 多要求样例:")
    for sn, mn, p in l3_conflict_samples:
        print(f"  {sn} | {mn} -> {p}")

    # ---- 专项/民族班剥离再查 ----
    strip_kw = ("教育部高校专项计划", "高校专项计划", "辽宁省高校专项计划",
                "民族班，只招少数民族考生", "民族班")
    extra = 0
    extra_samples = []
    still2 = []
    for sn, mn in still:
        t = norm1(mn)
        for kw in strip_kw:
            t = t.replace(f"({kw})", "")
        t = base_name(t)
        if (norm1(sn), t) in off_base:
            extra += 1
            if len(extra_samples) < 8:
                extra_samples.append((sn, mn, t))
        else:
            still2.append((sn, mn))
    print(f"\n专项/民族班剥离再查挽回 {extra}")
    for sn, mn, t in extra_samples:
        print(f"  {sn} | {mn} -> {t}")

    # ---- 残差 Top 学校官方专业抽样 ----
    print("\n== 残差 Top 学校：左=投档残差样例 / 右=官方专业名样例 ==")
    by_school = defaultdict(list)
    for sn, mn in still2:
        by_school[sn].append(mn)
    for sn, mns in sorted(by_school.items(), key=lambda kv: -len(kv[1]))[:12]:
        off_m = sorted(off_by_school_raw.get(norm1(sn), {}).keys())
        print(f"\n{sn}: 残差 {len(mns)} / 官方专业 {len(off_m)}")
        print(f"  残差样例: {mns[:4]}")
        print(f"  官方样例: {off_m[:6]}")

    # ---- 脏数据：school_name 疑似含专业 ----
    dirty = [(sn, mn) for sn, mn in units
             if re.search(r"[\u4e00-\u9fff]{2,}(学|院|大学)", sn or "")
             and ("专业" in sn or "临床医学" in sn)]
    print(f"\n脏数据 school_name 疑似含专业: {len(dirty)}")
    for sn, mn in dirty[:5]:
        print(f"  school={sn} major={mn}")


if __name__ == "__main__":
    main()
