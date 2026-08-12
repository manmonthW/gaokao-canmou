#!/usr/bin/env python3
"""
build_major_eval_map.py
=======================
生成并写入 本科专业名 → 第五轮学科评估学科名 映射表 (major_eval_map)。

规则：
  1) exact:  major_catalog.name 直接等于 school_disciplines.discipline_name
  2) category: 专业类(category) → 学科 的预定义映射（覆盖同名之外的学科）

依赖：
  - major_catalog  （本科专业字典）
  - school_disciplines(source='eval5_a', verify_status='verified')  （已入库的第五轮 A 类）
  - 迁移 0016_major_eval_map.sql 已执行（表存在）

用法：
  python3 etl/build_major_eval_map.py            # 写入（先清空再插入）
  python3 etl/build_major_eval_map.py --dry-run  # 只打印统计，不写库

说明：
  - category 映射字典覆盖常见本科专业类到一级学科口径，未覆盖的专业类不建立映射
    （这些专业暂无对应学科评估数据，详情页自然不展示评估区块）。
  - 同名映射优先级高（map_type='exact'），即便也在 category 映射中出现，也记为 exact。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from load import get_conn

# 专业类(category) → 第五轮学科评估学科名 映射
# 仅包含 school_disciplines 中实际存在的学科名
CATEGORY_TO_DISCIPLINE: dict[str, str] = {
    "计算机类": "计算机科学与技术",
    "软件工程": "软件工程",
    "电子信息类": "信息与通信工程",
    "机械类": "机械工程",
    "材料类": "材料科学与工程",
    "自动化类": "控制科学与工程",
    "电气类": "电气工程",
    "土木类": "土木工程",
    "建筑类": "建筑学",
    "交通运输类": "交通运输工程",
    "航空航天类": "航空宇航科学与技术",
    "兵器类": "兵器科学与技术",
    "化工与制药类": "化学工程与技术",
    "化学类": "化学",
    "环境科学与工程类": "环境科学与工程",
    "食品科学与工程类": "食品科学与工程",
    "矿业类": "矿业工程",
    "地质类": "地质学",
    "海洋工程类": "船舶与海洋工程",
    "农业工程类": "农业工程",
    "能源动力类": "动力工程及工程热物理",
    "力学类": "力学",
    "数学类": "数学",
    "物理类": "物理学",
    "生物科学类": "生物学",
    "地理科学类": "地理学",
    "大气科学类": "大气科学",
    "海洋科学类": "海洋科学",
    "地球物理学类": "地球物理学",
    "地质学类": "地质学",
    "生物工程类": "生物工程",
    "教育学类": "教育学",
    "体育学类": "体育学",
    "中国语言文学类": "中国语言文学",
    "外国语言文学类": "外国语言文学",
    "新闻传播学类": "新闻传播学",
    "历史学类": "中国史",
    "经济学类": "理论经济学",
    "金融学类": "应用经济学",
    "经济与贸易类": "应用经济学",
    "财政学类": "应用经济学",
    "工商管理类": "工商管理",
    "管理科学与工程类": "管理科学与工程",
    "公共管理类": "公共管理",
    "图书情报与档案管理类": "图书情报与档案管理",
    "法学类": "法学",
    "政治学类": "政治学",
    "社会学类": "社会学",
    "民族学类": "民族学",
    "马克思主义理论类": "马克思主义理论",
    "哲学类": "哲学",
    "公安学类": "公安学",
    "心理学类": "心理学",
    "统计学类": "统计学",
    "植物生产类": "作物学",
    "动物生产类": "畜牧学",
    "动物医学类": "兽医学",
    "水产类": "水产",
    "草学类": "草学",
    "林学类": "林学",
    "农业资源与环境类": "农业资源与环境",
    "基础医学类": "基础医学",
    "临床医学类": "临床医学",
    "口腔医学类": "口腔医学",
    "公共卫生与预防医学类": "公共卫生与预防医学",
    "药学类": "药学",
    "护理学类": "护理学",
    "医学技术类": "医学技术",
    "中药学类": "中药学",
    "中医学类": "中医学",
    "美术学类": "美术学",
    "设计学类": "设计学",
    "音乐与舞蹈学类": "音乐与舞蹈学",
    "戏剧与影视学类": "戏剧与影视学",
    "艺术学理论类": "艺术学理论",
    "风景园林类": "风景园林学",
    "生物医学工程类": "生物医学工程",
    "测绘类": "测绘科学与技术",
    "安全科学与工程类": "安全科学与工程",
    "电子信息类": "电子科学与技术",
    "轻工类": "轻工技术与工程",
    "林业工程类": "林业工程",
    "纺织类": "纺织科学与工程",
    "仪器类": "仪器科学与技术",
    "水利类": "水利工程",
    "自然保护与环境生态类": "农业资源与环境",
    "植物生产类": "植物保护",
}


def build_rows(cur):
    # 已入库的第五轮 A 类学科名（白名单，保证映射目标有效）
    cur.execute(
        "SELECT DISTINCT discipline_name FROM school_disciplines "
        "WHERE source='eval5_a' AND verify_status='verified'"
    )
    valid_disciplines = {r[0] for r in cur.fetchall()}

    # 仅保留目标学科确实存在的 category 映射
    cat_map = {k: v for k, v in CATEGORY_TO_DISCIPLINE.items() if v in valid_disciplines}

    cur.execute("SELECT name, category FROM major_catalog")
    majors = cur.fetchall()

    rows = []  # (major_name, eval_discipline, map_type)
    for name, cat in majors:
        if name in valid_disciplines:
            rows.append((name, name, "exact"))
        elif cat in cat_map:
            rows.append((name, cat_map[cat], "category"))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只打印统计，不写库")
    args = ap.parse_args()

    conn = get_conn()
    try:
        cur = conn.cursor()
        rows = build_rows(cur)
        exact = sum(1 for r in rows if r[2] == "exact")
        cat = sum(1 for r in rows if r[2] == "category")
        print(f"[build_major_eval_map] 生成映射 {len(rows)} 条 "
              f"(exact={exact}, category={cat})")

        if args.dry_run:
            # 打印前 20 条样例
            for r in rows[:20]:
                print("  ", r)
            return

        cur.execute("TRUNCATE major_eval_map")
        cur.executemany(
            "INSERT INTO major_eval_map (major_name, eval_discipline, map_type) "
            "VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            rows,
        )
        conn.commit()
        print(f"[build_major_eval_map] 已写入 {len(rows)} 条映射")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
