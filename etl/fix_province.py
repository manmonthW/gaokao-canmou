#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""补齐 school_profiles 中因城市名(民族自治州/兵团市)未匹配而缺失的 province。
改进归一化: 先去民族词, 再去 市/地区/自治州 等后缀, 与 brightgems 短名对齐。
"""
import os, io, csv, re, requests
import psycopg2
from config import DSN

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
CITY_CSV = "https://raw.githubusercontent.com/brightgems/china_city_dataset/master/china_city_list.csv"
SUFFIXES = ["市","地区","自治州","自治县","自治","盟","区","县","自治旗","特别行政区"]
ETHNIC = "维吾尔|哈萨克|蒙古|回|藏|壮|满|朝鲜|彝|苗|哈尼|布依|侗|黎|土家|白|傣|傈僳|佤|纳西|景颇|布朗|阿昌|怒|独龙|基诺|高山|俄罗斯|鄂温克|鄂伦春|达斡尔|保安|撒拉|东乡|裕固|锡伯|门巴|珞巴|羌|土|毛南|仫佬|京|赫哲"

def norm(c: str) -> str:
    c = (c or "").strip()
    c = re.sub(r"(" + ETHNIC + r")族", "", c)
    for s in SUFFIXES:
        if len(c) > len(s) and c.endswith(s):
            c = c[:-len(s)]
    return c

MANUAL = {  # brightgems 仍未覆盖的兵团市/省直管/县级市/自治州
    "昆玉":"新疆","图木舒克":"新疆","阿拉尔":"新疆","石河子":"新疆",
    "济源":"河南","昆山":"江苏","东方":"海南","襄阳":"湖北",
    "伊犁哈萨克":"新疆","博尔塔拉蒙古":"新疆","巴音郭楞蒙古":"新疆","陵水黎族自治":"海南",
}

def main():
    p = os.path.join(DATA, "city_list.csv")
    if not os.path.exists(p):
        r = requests.get(CITY_CSV, headers={"User-Agent": UA}, timeout=30); open(p,"wb").write(r.content)
    bmap = {}
    with open(p, "rb") as f:
        for row in csv.DictReader(io.StringIO(f.read().decode("gbk", "replace"))):
            bmap[norm(row.get("City",""))] = row.get("Province","").strip()

    conn = psycopg2.connect(DSN); cur = conn.cursor()
    cur.execute("SELECT code, city FROM school_profiles WHERE province IS NULL")
    rows = cur.fetchall()
    fixed = 0
    for code, city in rows:
        prov = bmap.get(norm(city)) or MANUAL.get(city) or MANUAL.get(norm(city))
        if prov:
            cur.execute("UPDATE school_profiles SET province=%s WHERE code=%s", (prov, code))
            fixed += 1
    conn.commit()
    cur.execute("SELECT count(*) FROM school_profiles WHERE province IS NULL")
    print(f"修复省份 {fixed} 条; 仍缺失省份: {cur.fetchone()[0]}")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
