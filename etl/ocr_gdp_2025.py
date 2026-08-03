#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
从三张 GDP 图片用 OCR(逐行切片放大)提取 城市->2025GDP。
策略: 图片为多列并排长表。把每张图按水平条带细切 + 放大 4 倍,
配合 psm=7 单行识别, 过滤出含中文城市名的行, 解析该行的数值。
输出 CSV: city,province_tag,gdp2025,gdp2024
"""
import pytesseract
from PIL import Image
import re, os, csv, sys

IMAGES = [
    "/home/ekewang/projects/gaokao/v2-e3683196f005ea652a58bb6251d46667_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-4cbf97872ed200f3099683bbed0bdbc7_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-b3c808e1f91365d56a4f41365b903220_1440w.jpg",
]

CITY_RE = re.compile(r"[\u4e00-\u9fff]{2,8}市|[\u4e00-\u9fff]{2,8}州|[\u4e00-\u9fff]{2,8}地区|[\u4e00-\u9fff]{2,8}盟")
PROV_RE = re.compile(r"([\u4e00-\u9fff]{2,6}省[\u4e00-\u9fff]?[\u4e00-\u9fff]?\d?|[\u4e00-\u9fff]{2,4}市\d?|[\u4e00-\u9fff]{2,4}区\d?|自治区\d?)")
NUM_RE = re.compile(r"\d{3,5}\.\d{1,2}")

def clean(s):
    # 去掉常见 OCR 噪声字符
    return re.sub(r"[^0-9.\u4e00-\u9fff]", "", s)

def extract_rows(img_path):
    img = Image.open(img_path).convert("L")
    w, h = img.size
    rows = []
    strip = 20
    # 左半 + 右半分别切, 覆盖多列
    for x0 in (0, w//2):
        half = img.crop((x0, 0, x0 + w//2, h))
        hw, hh = half.size
        for i in range(0, hh - strip, strip):
            c = half.crop((0, i, hw, i + strip)).resize((hw*4, strip*4))
            t = pytesseract.image_to_string(c, lang="chi_sim+eng", config="--psm 7")
            line = t.strip()
            if not line:
                continue
            if CITY_RE.search(line):
                # 提取城市名(第一个匹配)
                mcity = CITY_RE.search(line)
                city = mcity.group()
                # 省份标签: 取城市名之后的省份片段
                prov = ""
                after = line[mcity.end():]
                mp = PROV_RE.search(after)
                if mp:
                    prov = mp.group()
                # 数值: 取该行所有数字
                nums = NUM_RE.findall(line)
                rows.append({
                    "city": city,
                    "prov": prov,
                    "nums": nums,
                    "raw": line,
                })
    return rows

def main():
    out = []
    for f in IMAGES:
        print(f"[OCR] {os.path.basename(f)}", file=sys.stderr)
        rows = extract_rows(f)
        for r in rows:
            out.append(r)
    # 打印便于人工核对
    for r in out:
        print(f"{r['city']}\t{r['prov']}\t{r['nums']}\t{r['raw']}")
    # 写 CSV 备用
    with open("/home/ekewang/projects/gaokao/ln/etl/gdp2025_ocr_raw.csv", "w", newline="", encoding="utf-8") as fh:
        wcsv = csv.writer(fh)
        wcsv.writerow(["city", "prov", "nums", "raw"])
        for r in out:
            wcsv.writerow([r["city"], r["prov"], "|".join(r["nums"]), r["raw"]])

if __name__ == "__main__":
    main()
