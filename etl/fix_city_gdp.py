#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_city_gdp.py —— 用权威口径(2025年各地统计局公报)修正 cities 表中错误的 GDP 数据。

错误来源: 原数据取自 Wikidata, 单位/汇率混乱, 且大量城市为整百占位默认值(脏数据)。
已联网逐城核对 2025 年地区生产总值(亿元), 仅修正确认有误的城市。

用法:
  python fix_city_gdp.py            # dry-run 预览
  python fix_city_gdp.py --apply    # 写入库
"""
import os, sys, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

# city(数据库实际名称) -> 2025年GDP(亿元), 均来自各地统计局公报
CORRECT = {
    # 整百占位/错误(>=1000)
    "鄂尔多斯": 6122.21,
    "菏泽": 4937.4,
    "驻马店": 3501.64,
    "商丘": 3475.38,
    "信阳": 3196.70,
    "新乡": 3687.07,
    "许昌": 3583.4,
    "莆田": 3579.52,
    "上饶": 3935.9,
    "泸州": 3004.29,
    "红河哈尼族彝族": 3154.52,
    "红河": 3154.52,
    "赣州": 5221.29,
    "昆山": 5615.34,
    "邢台": 2800.8,
    "枣庄": 2502.52,
    "凉山彝族": 2605.75,
    "凉山": 2605.75,
    "衢州": 2401.63,
    "晋中": 2462.6,
    "大理白族": 2087.51,
    "大理": 2087.51,
    "遂宁": 2002.0,
    "黔南布依族苗族": 2008.49,
    "黔南": 2008.49,
    "呼伦贝尔": 1749.74,
    "眉山": 2008.72,
    "六盘水": 1777.75,
    "鞍山": 2180.4,
    "昌吉回族自治州": 2637.67,
    "昌吉": 2637.67,
    "楚雄彝族": 2040.17,
    "楚雄": 2040.17,
    "吕梁": 2575.02,
    "梧州": 1719.79,
    "湘西土家族苗族": 889.5,
    "湘西": 889.5,
    "黔东南苗族侗族": 1500.24,
    "黔东南": 1500.24,
    "朔州": 1303.7,
    "齐齐哈尔": 1402.1,
    "莱芜": 1057.38,
    "巴彦淖尔": 1277.6,
    "伊犁哈萨克": 3470.95,
    "伊犁": 3470.95,
    "崇左": 1358.64,
    "来宾": 1049.66,
    "鹰潭": 1459.41,
    "延边朝鲜族": 1064.08,
    "延边": 1064.08,
    # 整百占位(<1000)
    "七台河": 249.41,
    "伊春": 380.9,
    "双鸭山": 571.1,
    "鹤岗": 392.2,
    "四平": 600.0,
    "松原": 1030.6,
    "白山": 590.17,
    "辽源": 547.09,
    "通化": 709.3,
    "阜新": 651.8,
    "朝阳": 1156.7,
    "本溪": 1006.0,
    "东方": 285.37,
    "乌海": 540.75,
    "儋州": 1030.34,
    "吐鲁番": 668.1,
    "嘉峪关": 391.0,
    "巢湖": 620.3,
    "巴音郭楞蒙古": 1723.53,
    "巴音郭楞": 1723.53,
    "德宏傣族景颇族": 648.07,
    "德宏": 648.07,
    "怒江傈僳族": 288.98,
    "怒江": 288.98,
    "海东": 615.8,
    "甘南藏族": 275.62,
    "甘南": 275.62,
    "石河子": 862.0,
    "迪庆藏族": 316.65,
    "迪庆": 316.65,
    "阿拉善": 418.8,
    "陇南": 716.0,
    "兴安盟": 850.09,
    "兴安": 850.09,
    "博尔塔拉蒙古": 575.15,
    "博尔塔拉": 575.15,
    "图木舒克": 235.0,
    "昆玉": 38.0,
    "阿拉尔": 462.74,
    # 已知错误(单位差10倍)
    "南京": 19428.78,
    "常州": 11158.7,
    # 徐州 9957.22 经核对为正确值, 保持
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入库")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # 取库中现有城市名, 建立匹配
    cur.execute("SELECT city, gdp FROM cities WHERE gdp IS NOT NULL")
    db = {r[0]: float(r[1]) for r in cur.fetchall()}

    plans = []      # (city, old, new)
    nomatch = []    # CORRECT 中库里不存在的城市
    for city, new in CORRECT.items():
        if city in db:
            old = db[city]
            if abs(old - new) > 0.01:
                plans.append((city, old, new))
        else:
            nomatch.append(city)

    print(f"{'[DRY-RUN] ' if not args.apply else ''}将修正 {len(plans)} 个城市 GDP")
    if not args.apply:
        for city, old, new in sorted(plans, key=lambda x: x[0]):
            print(f"    {city}: {old:.2f} -> {new:.2f}")
    if nomatch:
        print(f"\n⚠ CORRECT 中有 {len(nomatch)} 个库里无对应行(已忽略): {nomatch}")

    if not args.apply:
        print("\n(加 --apply 写入)")
        cur.close(); conn.close(); return

    updated = 0
    for city, old, new in plans:
        cur.execute("UPDATE cities SET gdp=%s, gdp_year=2025 WHERE city=%s", (new, city))
        updated += 1
    conn.commit()
    print(f"\n已写入 {updated} 条 GDP 修正。")

    # 校验: 修正后是否还有整百默认值残留
    cur.execute("""SELECT city, gdp FROM cities
        WHERE gdp IS NOT NULL
          AND gdp::numeric = floor(gdp)
          AND (gdp::numeric % 100) = 0""")
    remain = cur.fetchall()
    print(f"修正后整百默认值残留: {len(remain)} 条")
    for c, g in remain:
        print(f"    残留 {c}: {g}")

    cur.close(); conn.close()


if __name__ == "__main__":
    main()
