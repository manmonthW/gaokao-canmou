#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""快速OCR: 先低分辨率粗扫定位含城市名的水平条带, 再对命中条带高精度放大OCR。"""
import pytesseract
from PIL import Image
import re, os, sys

IMAGES = [
    "/home/ekewang/projects/gaokao/v2-e3683196f005ea652a58bb6251d46667_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-4cbf97872ed200f3099683bbed0bdbc7_1440w.jpg",
    "/home/ekewang/projects/gaokao/v2-b3c808e1f91365d56a4f41365b903220_1440w.jpg",
]
CITY_RE = re.compile(r"[\u4e00-\u9fff]{2,8}(?:市|州|地区|盟)")
NUM_RE = re.compile(r"\d{3,5}\.\d{1,2}")

def ocr_full(img, scale=2):
    w, h = img.size
    big = img.resize((w*scale, h*scale))
    return pytesseract.image_to_string(big, lang="chi_sim+eng", config="--psm 6")

def extract(img_path):
    img = Image.open(img_path).convert("L")
    w, h = img.size
    raw = ocr_full(img, scale=2)
    out = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if CITY_RE.search(line):
            m = CITY_RE.search(line)
            city = m.group()
            nums = NUM_RE.findall(line)
            out.append((city, nums, line))
    return out

def main():
    for f in IMAGES:
        print(f"\n##### {os.path.basename(f)} #####", file=sys.stderr)
        rows = extract(f)
        for city, nums, line in rows:
            print(f"{city}\t{nums}\t{line}")

if __name__ == "__main__":
    main()
