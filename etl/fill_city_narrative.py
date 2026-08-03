#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fill_city_narrative.py —— 补齐 cities.note 城市叙述字段
规则: 风格(省份气候) + 产业(城市群产业) + 发展(分级)，生成标签化短描述(非长篇文案)。

用法:
  python fill_city_narrative.py            # 默认 dry-run，打印样例，不写库
  python fill_city_narrative.py --apply    # 写入 cities.note
"""
import os, argparse, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

# ── 1) 省份气候 -> 风格 ─────────────────────────────────────────────
REGION_CLIMATE = {
    "东北": "寒温带·冬季漫长·四季分明·冰雪资源",
    "华北": "温带季风·四季分明·春季多风·夏雨集中",
    "华东": "亚热带季风·温暖湿润·梅雨明显",
    "华中": "亚热带季风·湿热·四季分明",
    "华南": "亚热带/热带·温暖湿润·长夏无冬·多台风",
    "西南": "亚热带湿润·多雾·山地立体气候",
    "西北": "温带大陆性·干旱少雨·昼夜温差大·日照强",
}
# 省份级覆盖(更细)
PROV_CLIMATE_OVERRIDE = {
    "云南": "低纬高原·四季如春·干湿季分明",
    "重庆": "亚热带季风·湿热多雾·山城立体",
    "西藏": "高寒缺氧·日照强·昼夜温差大",
    "海南": "热带季风·长夏无冬·温热湿润",
    "内蒙古": "温带大陆性·草原辽阔·冬寒夏凉",
    "青海": "高寒·日照强·昼夜温差大",
    "新疆": "温带大陆性·极端干旱·昼夜温差极大",
}

# ── 2) 城市群 / 省份 -> 产业 ────────────────────────────────────────
CLUSTER_INDUSTRY = {
    "长三角": "金融·互联网·高端制造·外贸·生物医药",
    "珠三角": "电子信息·家电·先进制造·外贸·科创",
    "京津冀": "央企总部·政治文化·科技·金融",
    "成渝": "汽车·电子·装备制造·军工",
    "长江中游": "光电子·汽车·钢铁·工程机械",
    "关中平原": "航空航天·军工·科教·硬科技",
    "中原": "物流枢纽·食品加工·装备制造·电子",
    "山东半岛": "重工·化工·家电·海洋产业",
    "海西": "外贸·鞋服·民营经济·半导体",
    "辽中南": "装备制造·重工业·造船·软件",
    "哈长": "汽车·装备制造·农业科教",
    "滇中": "旅游·烟草·生物资源·康养",
    "黔中": "大数据·白酒·旅游",
    "北部湾": "面向东盟外贸·热带农业·旅游",
    "山西中部": "能源·煤炭·重工",
    "兰白": "石化·有色冶金·军工",
    "呼包鄂榆": "能源·乳业·稀土",
    "天山北坡": "能源·石化·边疆贸易",
    "宁夏沿黄": "能源·煤化工·枸杞",
    "兰西": "能源·盐湖化工·高原农牧",
}
# 省份级产业兜底(用于 "X·其他" 及未命中城市群的省份)
PROV_INDUSTRY = {
    "北京": "政治文化中心·科技·金融·互联网·总部经济",
    "天津": "装备制造·化工·港口物流·生物医药",
    "河北": "钢铁·建材·重工业·装备制造",
    "山西": "能源煤炭·重工·焦化",
    "内蒙古": "能源·稀土·乳业·畜牧",
    "辽宁": "装备制造·重工业·石化·造船",
    "吉林": "汽车·装备制造·农业·生物医药",
    "黑龙江": "装备制造·石油·农业·冰雪",
    "上海": "金融·互联网·高端制造·外贸·科创",
    "江苏": "高端制造·电子信息·装备制造·外贸",
    "浙江": "民营制造·电商·互联网·外贸",
    "安徽": "家电·汽车·建材·农业",
    "福建": "外贸·鞋服·民企·半导体",
    "江西": "有色金属·航空·电子信息·农业",
    "山东": "重工·化工·家电·海洋·农业",
    "河南": "食品加工·装备制造·农业·物流",
    "湖北": "汽车·光电子·钢铁·科教",
    "湖南": "工程机械·轨道交通·文化传媒·农业",
    "广东": "电子信息·家电·先进制造·外贸",
    "广西": "汽车·有色金属·制糖·面向东盟",
    "海南": "旅游·热带农业·自贸港·康养",
    "重庆": "汽车·电子信息·装备制造·山城",
    "四川": "装备制造·电子信息·白酒·农业",
    "贵州": "大数据·白酒·旅游·能源",
    "云南": "旅游·烟草·有色金属·农业",
    "西藏": "旅游·矿产·高原农牧",
    "陕西": "航空航天·军工·科教·能源化工",
    "甘肃": "能源·有色冶金·农业·风电",
    "青海": "能源·盐湖化工·高原农牧",
    "宁夏": "能源·煤化工·枸杞·农业",
    "新疆": "能源·棉花·农业·边疆贸易",
}

# ── 3) 分级 -> 发展 ────────────────────────────────────────────────
TIER_DEV = {
    "一线": "资源高度集聚·机会多·竞争激烈·高成本",
    "新一线": "新兴增长极·产业活跃·潜力大·性价比高",
    "二线": "区域中心·配套完善·宜居宜业",
    "三线": "生活成本低·节奏舒缓·宜居",
    "四线": "小城慢生活·成本极低·产业单一",
    "五线": "县域小城·生活安逸·产业薄弱",
}


def build_note(province, region, tier, cluster):
    # 风格 <- 省份气候
    climate = (PROV_CLIMATE_OVERRIDE.get(province)
               or REGION_CLIMATE.get(region)
               or "气候温和·四季分明")
    # 产业 <- 城市群产业(命中则用，否则省份兜底)
    if cluster and "·其他" not in cluster:
        industry = CLUSTER_INDUSTRY.get(cluster) or PROV_INDUSTRY.get(province)
    elif cluster and "·其他" in cluster:
        prov2 = cluster.split("·")[0]
        industry = PROV_INDUSTRY.get(prov2) or PROV_INDUSTRY.get(province)
    else:
        industry = PROV_INDUSTRY.get(province)
    industry = industry or "产业以本地资源与传统制造业为主"
    # 发展 <- 分级
    dev = TIER_DEV.get(tier) or "中小城市·发展平稳"
    return f"风格:{climate} | 产业:{industry} | 发展:{dev}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="写入库(默认仅预览)")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("SELECT city,province,region,tier,cluster FROM cities ORDER BY province,city")
    rows = cur.fetchall()

    out = []
    for city, province, region, tier, cluster in rows:
        note = build_note(province, region, tier, cluster)
        out.append((city, note))

    if not args.apply:
        print(f"[DRY-RUN] 共 {len(out)} 城，预览样例(前 24):\n")
        for city, note in out[:24]:
            print(f"  {city:<6} {note}")
        print("\n(加 --apply 写入 cities.note)")
    else:
        for city, note in out:
            cur.execute("UPDATE cities SET note=%s WHERE city=%s", (note, city))
        conn.commit()
        cur.execute("SELECT count(*) FROM cities WHERE note IS NOT NULL AND note<>''")
        n = cur.fetchone()[0]
        print(f"已写入 cities.note: {n}/{len(out)} 城")
    cur.close(); conn.close()


if __name__ == "__main__":
    main()
