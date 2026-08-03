#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_cities.py —— 城市画像自动化装载
数据源(均可直连, 无需反爬):
  1. brightgems/china_city_dataset (GitHub raw): 城市/省份/地理大区/分级(Tier)
  2. Wikidata SPARQL: 各城市 地区GDP(亿元) + 年份
  3. 规则推导: 城市群(cluster) / 是否沿海(coastal)
城市名归一化(去"市/地区/自治州/盟"等后缀)后, 与院校所在城市(教育部名单)对齐。
"""
import os, io, csv, time, requests
import psycopg2
from config import DSN

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
CITY_CSV = "https://raw.githubusercontent.com/brightgems/china_city_dataset/master/china_city_list.csv"
WD_SPARQL = "https://query.wikidata.org/sparql"

PROV_REGION = {
    "北京":"华北","天津":"华北","河北":"华北","山西":"华北","内蒙古":"华北",
    "辽宁":"东北","吉林":"东北","黑龙江":"东北",
    "上海":"华东","江苏":"华东","浙江":"华东","安徽":"华东","福建":"华东","江西":"华东","山东":"华东",
    "河南":"华中","湖北":"华中","湖南":"华中",
    "广东":"华南","广西":"华南","海南":"华南",
    "重庆":"西南","四川":"西南","贵州":"西南","云南":"西南","西藏":"西南",
    "陕西":"西北","甘肃":"西北","青海":"西北","宁夏":"西北","新疆":"西北",
}
COASTAL_PROV = {"辽宁","河北","天津","山东","江苏","上海","浙江","福建","广东","海南","广西","台湾","香港","澳门"}
CLUSTER = {
    "上海":"长三角","南京":"长三角","苏州":"长三角","无锡":"长三角","常州":"长三角","镇江":"长三角","扬州":"长三角","南通":"长三角","盐城":"长三角","泰州":"长三角","杭州":"长三角","宁波":"长三角","嘉兴":"长三角","湖州":"长三角","绍兴":"长三角","金华":"长三角","台州":"长三角","合肥":"长三角","芜湖":"长三角","舟山":"长三角",
    "深圳":"珠三角","广州":"珠三角","佛山":"珠三角","东莞":"珠三角","珠海":"珠三角","中山":"珠三角","惠州":"珠三角","江门":"珠三角","肇庆":"珠三角",
    "北京":"京津冀","天津":"京津冀","石家庄":"京津冀","唐山":"京津冀","保定":"京津冀","廊坊":"京津冀","沧州":"京津冀","秦皇岛":"京津冀","张家口":"京津冀","承德":"京津冀",
    "成都":"成渝","重庆":"成渝","绵阳":"成渝",
    "武汉":"长江中游","长沙":"长江中游","南昌":"长江中游","株洲":"长江中游","襄阳":"长江中游","宜昌":"长江中游",
    "西安":"关中平原","郑州":"中原","济南":"山东半岛","青岛":"山东半岛","烟台":"山东半岛","潍坊":"山东半岛","威海":"山东半岛","沈阳":"辽中南","大连":"辽中南","哈尔滨":"哈长","长春":"哈长","厦门":"海西","福州":"海西","泉州":"海西","昆明":"滇中","贵阳":"黔中","南宁":"北部湾","海口":"北部湾","太原":"山西中部","兰州":"兰白","呼和浩特":"呼包鄂榆","乌鲁木齐":"天山北坡","银川":"宁夏沿黄","西宁":"兰西",
}
SUFFIXES = ["市","地区","自治州","盟","区","县","自治旗","特别行政区"]

def norm(c: str) -> str:
    c = (c or "").strip()
    for s in SUFFIXES:
        if len(c) > len(s) and c.endswith(s):
            c = c[:-len(s)]
    return c

def tier_map(t: str) -> str:
    t = (t or "").strip()
    if "new" in t.lower():
        return "新一线"
    for k, v in [("tier 1","一线"),("tier 2","二线"),("tier 3","三线"),("tier 4","四线"),("tier 5","五线")]:
        if k in t.lower():
            return v
    return t or None

def download_csv():
    p = os.path.join(DATA, "city_list.csv")
    if not os.path.exists(p):
        r = requests.get(CITY_CSV, headers={"User-Agent": UA}, timeout=30)
        r.raise_for_status()
        open(p, "wb").write(r.content)
    return p

def wikidata_gdp_batch(cities):
    """批量查询城市GDP(亿元)。cities: list[str]。返回 {city: (gdp, year)}"""
    out = {}
    # 每个城市用 "名" 与 "名市" 两种 label 兜底
    labels = []
    for c in cities:
        labels.append(c)
        labels.append(c + "市")
    vals = " ".join(f'"{l}"' for l in labels)
    q = f'''SELECT ?label ?gdp ?y WHERE {{
      VALUES ?label {{ {vals} }}
      ?c rdfs:label ?label .
      ?c wdt:P31/wdt:P279* wd:Q515 .
      ?c p:P2131 [ ps:P2131 ?gdp; pq:P585 ?t ] .
      BIND(YEAR(?t) AS ?y)
    }}'''
    try:
        r = requests.get(WD_SPARQL, params={"query": q},
                          headers={"User-Agent": UA, "Accept": "application/sparql-results+json"}, timeout=60)
        best = {}
        for b in r.json().get("results", {}).get("bindings", []):
            lab = b["label"]["value"]
            base = lab[:-1] if lab.endswith("市") else lab
            g = float(b["gdp"]["value"]); y = int(b["y"]["value"])
            if g >= 1e8:
                g = round(g / 1e8, 1)
            if base not in best or y > best[base][1]:
                best[base] = (g, y)
        out.update(best)
    except Exception as e:
        print("  batch GDP 查询异常:", e)
    return out

def main():
    p = download_csv()
    rows = []
    with open(p, "rb") as f:
        data = f.read().decode("gbk", errors="replace")
    for row in csv.DictReader(io.StringIO(data)):
        cn = norm(row.get("City", ""))
        if not cn:
            continue
        prov = row.get("Province", "").strip()
        tier = tier_map(row.get("Tier", ""))
        region = PROV_REGION.get(prov)
        cluster = CLUSTER.get(cn, (prov + "·其他") if prov else "其他")
        coastal = prov in COASTAL_PROV
        rows.append((cn, prov, region, tier, cluster, coastal))
    print(f"解析城市 {len(rows)} 个")

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS cities (
        city TEXT PRIMARY KEY, province TEXT, region TEXT, tier TEXT,
        gdp NUMERIC, gdp_year SMALLINT, cluster TEXT, coastal BOOLEAN, note TEXT)""")
    for cn, prov, region, tier, cluster, coastal in rows:
        cur.execute("""INSERT INTO cities (city,province,region,tier,cluster,coastal)
                       VALUES (%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (city) DO UPDATE SET
                         province=EXCLUDED.province, region=EXCLUDED.region,
                         tier=EXCLUDED.tier, cluster=EXCLUDED.cluster, coastal=EXCLUDED.coastal""",
                   (cn, prov, region, tier, cluster, coastal))
    conn.commit()
    print("写入 cities 基础信息完成")

    # Wikidata GDP 批量补录
    cur.execute("SELECT city FROM cities WHERE gdp IS NULL ORDER BY city")
    cities = [r[0] for r in cur.fetchall()]
    ok = 0
    BATCH = 50
    for i in range(0, len(cities), BATCH):
        chunk = cities[i:i+BATCH]
        res = wikidata_gdp_batch(chunk)
        for c in chunk:
            if c in res:
                g, yr = res[c]
                cur.execute("UPDATE cities SET gdp=%s, gdp_year=%s WHERE city=%s", (g, yr, c))
                ok += 1
        conn.commit()
        print(f"  GDP 进度 {min(i+BATCH,len(cities))}/{len(cities)} 已得 {ok}")
        time.sleep(0.3)
    cur.execute("SELECT count(*), count(gdp) FROM cities")
    tot, withg = cur.fetchone()
    print(f"城市画像完成: 共 {tot} 城, 其中 {withg} 城已含GDP")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
