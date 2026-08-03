#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
correct_city_data.py —— 校正 cities 表分级与缺失数据
基准: 第一财经《2025新一线城市魅力排行榜》(2025-05-28)
  一线(4): 上海 北京 深圳 广州
  新一线(15): 成都 杭州 重庆 武汉 苏州 西安 南京 长沙 郑州 天津 合肥 青岛 东莞 宁波 佛山
  二线(30): 济南 无锡 沈阳 昆明 福州 厦门 温州 石家庄 大连 哈尔滨 金华 泉州 南宁 长春
            常州 南昌 南通 贵阳 嘉兴 徐州 惠州 太原 烟台 临沂 保定 台州 绍兴 珠海 洛阳 潍坊

用法:
  python correct_city_data.py            # dry-run 打印将要做的改动
  python correct_city_data.py --apply    # 实际写入
"""
import os, argparse, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

# ── 1) 分级错配修正(权威 2025 名单) ──────────────────────────────────
# 仅覆盖可权威判定者；三线及以下长尾沿用源数据(已内部一致)。
CORRECT_TIER = {
    # 应为 一线
    "北京": "一线",
    # 应为 新一线(源数据被压低)
    "成都": "新一线", "合肥": "新一线", "佛山": "新一线",
    # 应为 二线(源数据误标更高或更低)
    "沈阳": "二线", "大连": "二线", "厦门": "二线",
    "临沂": "二线", "保定": "二线", "洛阳": "二线", "潍坊": "二线",
    # 源数据误标为二线，但 2025 名单未入二线 -> 降为三线
    "中山": "三线", "乌鲁木齐": "三线", "兰州": "三线", "海口": "三线",
}

# ── 2) 补全 23 个 tier 为空且基础信息缺失的城市 ──────────────────────
# (province, region, tier, cluster, coastal)
MISSING = {
    "东方":            ("海南", "华南", "五线", "海南·其他", True),
    "伊犁哈萨克":      ("新疆", "西北", "五线", "新疆·其他", False),
    "凉山彝族":        ("四川", "西南", "五线", "四川·其他", False),
    "博尔塔拉蒙古":    ("新疆", "西北", "五线", "新疆·其他", False),
    "图木舒克":        ("新疆", "西北", "五线", "新疆·其他", False),
    "大理白族":        ("云南", "西南", "四线", "云南·其他", False),
    "巴音郭楞蒙古":    ("新疆", "西北", "五线", "新疆·其他", False),
    "延边朝鲜族":      ("吉林", "东北", "四线", "吉林·其他", False),
    "恩施土家族苗族":  ("湖北", "华中", "四线", "湖北·其他", False),
    "昆山":            ("江苏", "华东", "三线", "长三角", False),
    "昆玉":            ("新疆", "西北", "五线", "新疆·其他", False),
    "昌吉回族":        ("新疆", "西北", "五线", "新疆·其他", False),
    "楚雄彝族":        ("云南", "西南", "五线", "云南·其他", False),
    "济源":            ("河南", "华中", "四线", "河南·其他", False),
    "湘西土家族苗族":  ("湖南", "华中", "四线", "湖南·其他", False),
    "甘南藏族":        ("甘肃", "西北", "五线", "甘肃·其他", False),
    "石河子":          ("新疆", "西北", "四线", "新疆·其他", False),
    "红河哈尼族彝族":  ("云南", "西南", "四线", "云南·其他", False),
    "襄阳":            ("湖北", "华中", "三线", "湖北·其他", False),
    "阿拉尔":          ("新疆", "西北", "五线", "新疆·其他", False),
    "陵水黎族自治":    ("海南", "华南", "四线", "海南·其他", True),
    "黔东南苗族侗族":  ("贵州", "西南", "五线", "贵州·其他", False),
    "黔南布依族苗族":  ("贵州", "西南", "五线", "贵州·其他", False),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入库(默认仅预览)")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    plans = []  # (city, field, old, new)

    # 分级修正
    for city, new_tier in CORRECT_TIER.items():
        cur.execute("SELECT tier FROM cities WHERE city=%s", (city,))
        row = cur.fetchone()
        old = row[0] if row else None
        if row is None:
            plans.append((city, "tier", "(不存在)", new_tier))
        elif old != new_tier:
            plans.append((city, "tier", old, new_tier))

    # 缺失城市补全
    for city, (prov, region, tier, cluster, coastal) in MISSING.items():
        cur.execute(
            "SELECT province,region,tier,cluster,coastal FROM cities WHERE city=%s",
            (city,))
        row = cur.fetchone()
        if row is None:
            plans.append((city, "全部", "(不存在)", f"{prov}/{region}/{tier}/{cluster}/{coastal}"))
            continue
        oprov, oregion, otier, ocluster, ocoastal = row
        if (oprov, oregion, otier, ocluster, ocoastal) != (prov, region, tier, cluster, coastal):
            plans.append((city, "基础信息",
                          f"{oprov}/{oregion}/{otier}/{ocluster}/{ocoastal}",
                          f"{prov}/{region}/{tier}/{cluster}/{coastal}"))

    if not plans:
        print("无需改动，数据已与权威名单一致。")
        cur.close(); conn.close(); return

    print(f"{'[DRY-RUN] ' if not args.apply else ''}将执行 {len(plans)} 项校正:\n")
    for city, field, old, new in plans:
        print(f"  {city:<10} [{field}]  {old}  ->  {new}")

    if not args.apply:
        print("\n(加 --apply 写入)")
        cur.close(); conn.close(); return

    for city, new_tier in CORRECT_TIER.items():
        cur.execute("UPDATE cities SET tier=%s WHERE city=%s", (new_tier, city))
    for city, (prov, region, tier, cluster, coastal) in MISSING.items():
        cur.execute(
            """UPDATE cities SET province=%s, region=%s, tier=%s, cluster=%s, coastal=%s
               WHERE city=%s""",
            (prov, region, tier, cluster, coastal, city))
    conn.commit()
    print(f"\n已写入 {len(plans)} 项校正。")
    cur.close(); conn.close()


if __name__ == "__main__":
    main()
