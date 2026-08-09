#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify_aliases.py —— 别名表目标存在性验证（只读）。

核对两件事：
1. 拟固化的别名表里，每个目标官方校名是否真的存在于 2027 选科表；
2. 三个存疑案例（大连工程学院 / 淮安大学 / 岳阳学院）用 LIKE 探测官方表。
"""
import psycopg2

from config import DSN

YEAR = 2027

ALIASES = {
    # 2026 更名（官方表仍用旧名）
    "吉林化工大学": "吉林化工学院",
    "天水师范大学": "天水师范学院",
    "湖南理工大学": "湖南理工学院",
    "湖州师范大学": "湖州师范学院",
    "闽江大学": "闽江学院",
    "赤峰大学": "赤峰学院",
    "西藏农牧大学": "西藏农牧学院",
    "桂林医科大学": "桂林医学院",
    "应急管理大学": "华北科技学院",
    # 职业大学升级（官方表仍用学院名）
    "武汉职业技术大学": "武汉职业技术学院",
    "成都航空职业技术大学": "成都航空职业技术学院",
    "吉林铁道职业技术大学": "吉林铁道职业技术学院",
    "酒泉职业技术大学": "酒泉职业技术学院",
    "深圳信息职业技术大学": "深圳信息职业技术学院",
    "黄河水利职业技术大学": "黄河水利职业技术学院",
    "黑龙江农业工程职业技术大学": "黑龙江农业工程职业学院",
    "长春职业技术大学": "长春职业技术学院",
    "兴安职业技术大学": "兴安职业技术学院",
    "新疆工业职业技术大学": "新疆工业职业技术学院",
    # 投档库笔误
    "辽宁师范大学高等专科学校": "辽宁师范高等专科学校",
}


def main():
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    targets = sorted(set(ALIASES.values()))
    cur.execute(
        """SELECT school_name, count(*) FROM subject_requirements
           WHERE year=%s AND school_name = ANY(%s)
           GROUP BY school_name""", (YEAR, targets))
    found = dict(cur.fetchall())

    print("== 别名目标存在性 ==")
    missing = []
    for src, dst in ALIASES.items():
        ok = dst in found
        print(f"  {'OK ' if ok else 'MISS'}  {src} -> {dst}"
              + (f" ({found[dst]} 行)" if ok else ""))
        if not ok:
            missing.append(dst)
    # 源校名在投档库的单元数（确认值得做别名）
    cur.execute(
        """SELECT school_name, count(DISTINCT major_name) FROM admission_scores
           WHERE year IN (2025,2026) AND school_name = ANY(%s)
           GROUP BY school_name""", (sorted(ALIASES),))
    adm = dict(cur.fetchall())
    print("\n== 源校名投档库专业单元数 ==")
    for s, n in sorted(adm.items()):
        print(f"  {s}: {n}")

    print("\n== 存疑案例 LIKE 探测 ==")
    for pat, label in [("大连%工%", "大连工程学院?"),
                       ("%淮安%", "淮安大学?"),
                       ("%岳阳%", "岳阳学院?"),
                       ("%惠州%", "惠州学院?"),
                       ("%苏州工%", "苏州工学院?"),
                       ("%绍兴%", "绍兴大学?")]:
        cur.execute(
            """SELECT school_name, count(*) FROM subject_requirements
               WHERE year=%s AND school_name LIKE %s
               GROUP BY school_name ORDER BY 2 DESC LIMIT 5""", (YEAR, pat))
        rows = cur.fetchall()
        print(f"  {label}  pattern={pat}: {rows or '无'}")
    conn.close()

    print(f"\n缺失目标 {len(missing)}: {missing}")


if __name__ == "__main__":
    main()
