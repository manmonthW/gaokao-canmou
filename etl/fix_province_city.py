#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_province_city.py —— 修正 school_profiles.province 误存为"城市名+市/州/盟/地区"的问题。

问题: 部分院校的 province 字段被写入了城市名(如 北京市/三亚市/乌鲁木齐市),
      而非真正的省份(北京/海南/新疆)。城市名应只出现在 city 字段。

修正策略:
  1) 借助已正确维护的 cities 表(city -> province)反查, 以 school_profiles.city 为键覆盖。
  2) 兜底: 自治州/地区/盟 等行政区级 city 不在 cities 表, 直接按其行政区划归属省份。

用法:
  python fix_province_city.py            # dry-run 打印预览
  python fix_province_city.py --apply    # 写入库
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

# 自治州/地区/盟 -> 省份(均为唯一明确的省级归属)
REGION_PROV = {
    "伊犁哈萨克自治州": "新疆", "兴安盟": "内蒙古", "凉山彝族自治州": "四川",
    "博尔塔拉蒙古自治州": "新疆", "和田地区": "新疆", "喀什地区": "新疆",
    "大兴安岭地区": "黑龙江", "大理白族自治州": "云南", "巴音郭楞蒙古自治州": "新疆",
    "延边朝鲜族自治州": "吉林", "恩施土家族苗族自治州": "湖北", "昌吉回族自治州": "新疆",
    "湘西土家族苗族自治州": "湖南", "甘南藏族自治州": "甘肃",
    "红河哈尼族彝族自治州": "云南", "锡林郭勒盟": "内蒙古", "阿克苏地区": "新疆",
    "黔东南苗族侗族自治州": "贵州", "黔南布依族苗族自治州": "贵州",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入库(默认仅预览)")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    plans = []  # (code, name, old, new)

    # 1) cities 表反查
    cur.execute("""
        SELECT sp.code, sp.name, sp.province AS old_prov, c.province AS new_prov
        FROM school_profiles sp
        JOIN cities c ON c.city = sp.city
        WHERE (sp.province LIKE '%市' OR sp.province LIKE '%地区'
               OR sp.province LIKE '%自治州' OR sp.province LIKE '%盟')
          AND c.province IS NOT NULL
          AND c.province <> sp.province
    """)
    plans.extend(cur.fetchall())

    # 2) 兜底: 自治州/地区/盟 直接映射
    cur.execute("""
        SELECT code, name, province FROM school_profiles
        WHERE province LIKE '%市' OR province LIKE '%地区'
           OR province LIKE '%自治州' OR province LIKE '%盟'
    """)
    for code, name, bad in cur.fetchall():
        new = REGION_PROV.get(bad)
        if new and (code, name, bad, new) not in plans:
            plans.append((code, name, bad, new))

    # 仍有无法覆盖的(需人工): 取所有带后缀的 province, 过滤掉已能映射的
    cur.execute("""
        SELECT code, name, province, city FROM school_profiles
        WHERE (province LIKE '%市' OR province LIKE '%地区'
               OR province LIKE '%自治州' OR province LIKE '%盟')
    """)
    covered_keys = {p[2] for p in plans}
    uncovered = [r for r in cur.fetchall() if r[2] not in covered_keys]

    plans.sort(key=lambda r: (r[2], r[0]))
    print(f"{'[DRY-RUN] ' if not args.apply else ''}"
          f"将修正 {len(plans)} 条省份(城市名 -> 真实省份)")
    if not args.apply:
        print("  样例(前 30 条):")
        for code, name, old, new in plans[:30]:
            print(f"    {code} {name}: {old} -> {new}")

    if uncovered:
        print(f"\n⚠ 仍有 {len(uncovered)} 条无法自动修正(需人工处理):")
        for code, name, bad, city in uncovered:
            print(f"    {code} {name}: province={bad} city={city}")

    if not args.apply:
        print("\n(加 --apply 写入)")
        cur.close(); conn.close(); return

    updated = 0
    for code, name, old, new in plans:
        cur.execute("UPDATE school_profiles SET province=%s WHERE code=%s", (new, code))
        updated += 1
    conn.commit()
    print(f"\n已写入 {updated} 条省份修正。")

    cur.execute("""
        SELECT count(*) FROM school_profiles
        WHERE province LIKE '%市' OR province LIKE '%地区'
           OR province LIKE '%自治州' OR province LIKE '%盟'
    """)
    remain = cur.fetchone()[0]
    print(f"修正后残留误存省份条数: {remain}")
    if remain:
        cur.execute("""
            SELECT province, count(*) FROM school_profiles
            WHERE province LIKE '%市' OR province LIKE '%地区'
               OR province LIKE '%自治州' OR province LIKE '%盟'
            GROUP BY province
        """)
        print("  残留值:", cur.fetchall())

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
