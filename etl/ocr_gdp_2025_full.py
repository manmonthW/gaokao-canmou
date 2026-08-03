#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCR 三张 2025 城市 GDP 图 -> 解析 城市/2025/2024/排名 -> 匹配 cities 表 -> 更新 gdp/gdp_year/note。
解析规则(基于实测 OCR 行格式):
  行样例: "大连市  辽宁省1  10002.10 9540.20 4.84% 5.70% 461.  30  1 ..."
  取: 首个中文城市名 = city; 城市名后第一组 \d{3,5}\.\d{1,2} = 2025GDP; 第二组 = 2024GDP
  排名列通常靠后(单列数字), 不强制。
只更新能稳定匹配到 cities.city 的行。
"""
import pytesseract, re, os, sys
from PIL import Image
import psycopg2

IMAGES = [
    "/home/ekewang/projects/gaokao/v2-e3683196f005ea652a58bb6251d46667_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-4cbf97872ed200f3099683bbed0bdbc7_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-b3c808e1f91365d56a4f41365b903220_1440w.jpg",
]
CITY_RE = re.compile(r"([\u4e00-\u9fff]{2,8}(?:市|州|地区|盟)|[\u4e00-\u9fff]{2,4}地区)")
# 匹配带小数点数 或 纯整数(末两位视为小数)
NUM_RE = re.compile(r"(\d{3,5}\.\d{1,2}|\d{4,6})")

def to_val(s):
    if "." in s:
        return float(s)
    # 整数: 末两位当小数 (如 264887 -> 2648.87)
    return float(s[:-2] + "." + s[-2:]) if len(s) >= 3 else float(s)

# OCR 错字 -> 正确 city(去后缀版)
OCR_FIX = {
    "洪江": "衡阳",        # 衡阳误识
    "曲请": "曲靖",
    "欧州": "温州",
    "油头": "汕头",
    "萌阳": "濮阳",
    "多壁": "亳州",
    "临沦": "临沧",
    "铁怜": "铁岭",
    "和困": "和田",
    "次山": "台山",
    "湘漂": "湘潭",
    "黄内": "黄冈",
    "已中": "巴中",
    "填南": "海南",        # 海南藏族自治州 -> 海南
    "勒苏": "克孜勒苏",    # 克孜勒苏柯尔克孜 -> 克孜勒苏柯尔克孜
    "博泵塔拉": "博尔塔拉",
    "西双版纳傣族自治": "西双版纳",
    "博泵塔拉蒙古自治": "博尔塔拉",
    "台山": "台山",
    "巴摩淖尔": "巴音郭楞",
    "海南藏族自治州": "海南",
    "克孜勒苏柯尔克孜自治州": "克孜勒苏柯尔克孜",
    "海北藏族自治州": "海北",
    "大兴安岭地区": "大兴安岭",
    "昌都市": "昌都",
    "固原市": "固原",
    "填南藏族自治": "海南",
    "勒苏柯尔克孜自治": "克孜勒苏柯尔克孜",
    "鸟兰察布": "乌兰察布",
    "文山壮族苗族自治": "文山",
    "西蒙古族藏族自治": "海西",
    "西土家族苗族自治": "湘西",
    "海南藏族自治": "海南",
    "海北藏族自治": "海北",
    "黄南藏族自治": "黄南",
    "后州": "湖州",
    "宿迁": "宿迁",        # 数值异常, 单独处理
}
SUFFIX = ("市", "州", "地区", "盟", "壮族苗族自治", "蒙古族藏族自治",
          "土家族苗族自治", "藏族自治", "柯尔克孜自治", "傣族自治",
          "蒙古自治")

def ocr_lines(img_path):
    img = Image.open(img_path).convert("L")
    w, h = img.size
    big = img.resize((w*2, h*2))
    txt = pytesseract.image_to_string(big, lang="chi_sim+eng", config="--psm 6")
    return [l.strip() for l in txt.splitlines() if l.strip()]

def parse(line):
    m = CITY_RE.search(line)
    if not m:
        return None
    city = m.group()
    # 去后缀
    for s in SUFFIX:
        if city.endswith(s):
            city = city[:-len(s)]
            break
    # 错字修正
    city = OCR_FIX.get(city, city)
    # 城市名之后取数值, 取第一个落在合理区间(500~20000)的作为2025
    after = line[m.end():]
    raw = NUM_RE.findall(after)
    nums = [to_val(x) for x in raw]
    if len(nums) < 1:
        return None
    gdp2025 = None
    gdp2024 = None
    for v in nums:
        if 100 <= v <= 60000:
            if gdp2025 is None:
                gdp2025 = v
            elif gdp2024 is None:
                gdp2024 = v
                break
    if gdp2025 is None:
        return None
    return city, gdp2025, gdp2024

def main():
    parsed = {}  # city -> (gdp2025, gdp2024)
    for f in IMAGES:
        print(f"[OCR] {os.path.basename(f)}", file=sys.stderr)
        for line in ocr_lines(f):
            r = parse(line)
            if r:
                city, g25, g24 = r
                # 同一城市多图出现, 取较大的2025(更可能是完整版)
                if city not in parsed or g25 > parsed[city][0]:
                    parsed[city] = (g25, g24)

    print(f"[解析] 共 {len(parsed)} 个城市行", file=sys.stderr)

    conn = psycopg2.connect(host="localhost", dbname="gaokao", user="gaokao",
                            password="gaokao123")
    cur = conn.cursor()
    cur.execute("SELECT city FROM cities")
    db_cities = set(r[0] for r in cur.fetchall())

    matched, unmatched = 0, 0
    # 允许超过20000亿的顶级城市白名单(真实2025 GDP>2万亿)
    TOP_ALLOW = {"上海","北京","深圳","重庆","广州","苏州","成都","杭州","武汉",
                 "南京","宁波","天津","青岛","无锡","长沙","郑州","佛山","福州",
                 "济南","合肥","西安","泉州","南通","东莞","常州","唐山","徐州",
                 "温州","大连","沈阳"}
    for city, (g25, g24) in parsed.items():
        if g25 > 20000 and city not in TOP_ALLOW:
            print(f"  [污染丢弃] {city} = {g25} (非顶级城却>2万亿)", file=sys.stderr)
            continue
        if city in db_cities:
            cur.execute(
                "UPDATE cities SET gdp=%s, gdp_year=2025, note='2025城市GDP年报(OCR)' WHERE city=%s",
                (g25, city))
            matched += 1
        else:
            unmatched += 1
            print(f"  [未匹配] {city} = {g25}", file=sys.stderr)
    conn.commit()
    cur.execute("SELECT count(*) FROM cities WHERE gdp IS NOT NULL AND gdp_year=2025")
    cov = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM cities")
    total = cur.fetchone()[0]
    print(f"[完成] 匹配更新 {matched} 城, 未匹配 {unmatched} 城; 当前2025GDP覆盖 {cov}/{total}", file=sys.stderr)
    conn.close()

if __name__ == "__main__":
    main()
