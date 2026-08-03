#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_school_profiles.py —— 院校画像自动化装载(核心维度)
数据源: 教育部《2025全国高等学校名单》Excel (moe.gov.cn, 直连可达)
  - 所在城市(所在地, 城市级) / 省份(derive) / 主管部门 / 办学层次 / 性质(备注)
  - 类型(综合/理工/师范…) 由校名启发式推导
  - 与 schools.code 通过 "标识码末4位 == code" 精确关联
仅装载出现在本校招生库(schools)中的院校(1594所)。
"""
import os, re, requests
import psycopg2, xlrd
from config import DSN

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
MOE_XLS = "https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A03/202506/W020250729615142156867.xls"
SUFFIXES = ["市","地区","自治州","盟","区","县","自治旗","特别行政区"]

def norm(c: str) -> str:
    c = (c or "").strip()
    for s in SUFFIXES:
        if len(c) > len(s) and c.endswith(s):
            c = c[:-len(s)]
    return c

def derive_type(name: str) -> str:
    n = name or ""
    rules = [
        ("师范", "师范"), ("医药","医药"), ("医科","医药"), ("医学","医药"),
        ("财经","财经"), ("经贸","财经"), ("金融","财经"),
        ("农林","农林"), ("农业","农林"), ("林业","农林"),
        ("政法","政法"), ("公安","政法"), ("警务","政法"),
        ("外国语","语言"), ("外语","语言"), ("语言","语言"),
        ("民族","民族"),
        ("艺术","艺术"), ("美术","艺术"), ("音乐","艺术"), ("戏剧","艺术"), ("传媒","艺术"), ("电影","艺术"), ("戏曲","艺术"),
        ("体育","体育"),
        ("军事","军事"), ("国防","军事"), ("武警","军事"),
        ("职业技术","职业技术"), ("职业","职业技术"), ("技师","职业技术"),
        ("理工","理工"), ("工业","理工"), ("科技","理工"), ("工程","理工"), ("交通","理工"),
        ("建筑","理工"), ("邮电","理工"), ("航空","理工"), ("航天","理工"), ("电子","理工"),
        ("信息","理工"), ("化工","理工"), ("矿业","理工"), ("石油","理工"), ("电力","理工"),
        ("水利","理工"), ("海洋","理工"), ("海事","理工"), ("测绘","理工"), ("地质","理工"),
        ("机电","理工"), ("汽车","理工"), ("铁道","理工"), ("冶金","理工"),
    ]
    for kw, t in rules:
        if kw in n:
            return t
    return "综合"

def derive_nature(remark: str) -> str:
    r = remark or ""
    if "民办" in r: return "民办"
    if "独立学院" in r: return "独立学院"
    if "中外合作" in r or "内地与港澳" in r or "境外" in r: return "中外合作办学"
    return "公办"

def download_xls():
    p = os.path.join(DATA, "moe_univ_2025.xls")
    if not os.path.exists(p):
        r = requests.get(MOE_XLS, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        open(p, "wb").write(r.content)
    return p

def main():
    p = download_xls()
    wb = xlrd.open_workbook(p)
    ws = wb.sheet_by_index(0)
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    parsed = 0; matched = 0; inserted = 0
    for r in range(ws.nrows):
        seq = ws.cell_value(r, 0)
        name = ws.cell_value(r, 1)
        if not (isinstance(seq, (int, float)) and str(name).strip()):
            continue  # 跳过表头/省份分组行
        parsed += 1
        code10 = str(int(ws.cell_value(r, 2)))
        code4 = code10[-4:]
        cur.execute("SELECT 1 FROM schools WHERE code=%s", (code4,))
        if not cur.fetchone():
            continue
        matched += 1
        affiliation = str(ws.cell_value(r, 3)).strip()
        city = norm(str(ws.cell_value(r, 4)))
        level = "本科" if "本科" in str(ws.cell_value(r, 5)) else "高职专科"
        remark = str(ws.cell_value(r, 6)).strip()
        nature = derive_nature(remark)
        stype = derive_type(name)

        # 确保 cities 有该城市(基础行, province 后续由 load_cities 补齐)
        cur.execute("INSERT INTO cities (city) VALUES (%s) ON CONFLICT (city) DO NOTHING", (city,))
        # 取 province
        cur.execute("SELECT province FROM cities WHERE city=%s", (city,))
        row = cur.fetchone()
        province = row[0] if row else None

        cur.execute("""INSERT INTO school_profiles
            (code,name,city,province,affiliation,level,nature,type,note)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (code) DO UPDATE SET
              name=EXCLUDED.name, city=EXCLUDED.city, province=EXCLUDED.province,
              affiliation=EXCLUDED.affiliation, level=EXCLUDED.level,
              nature=EXCLUDED.nature, type=EXCLUDED.type,
              note=CASE WHEN school_profiles.note IS NULL THEN EXCLUDED.note ELSE school_profiles.note END""",
            (code4, name, city, province, affiliation, level, nature, stype,
             (remark if remark and remark not in ("公办",) else None)))
        inserted += 1

    conn.commit()
    cur.execute("SELECT count(*) FROM school_profiles")
    tot = cur.fetchone()[0]
    print(f"教育部名单解析 {parsed} 行, 命中本校库 {matched} 所, 写入/更新 {inserted} 条; school_profiles 现有 {tot} 条")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
