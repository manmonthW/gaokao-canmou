# -*- coding: utf-8 -*-
"""OCR 扫描热门大学介绍全部卡片图，定位含『亦酒/非酒』或四大标签的图。"""
import os, glob, subprocess

BASE = "/home/ekewang/projects/gaokao/ln/2026allmaterial/热门大学介绍"
KEYS = ("亦酒", "非酒", "五院四系", "两电一邮", "国防七子")
hits = []
n = 0
for cat in sorted(os.listdir(BASE)):
    d = os.path.join(BASE, cat)
    if not os.path.isdir(d):
        continue
    for fp in sorted(glob.glob(os.path.join(d, "*.png"))):
        n += 1
        out = subprocess.run(["tesseract", fp, "stdout", "-l", "chi_sim+eng"],
                             capture_output=True, text=True).stdout
        got = [k for k in KEYS if k in out]
        if got:
            # 抓取命中行的上下文
            ctx = [ln.strip() for ln in out.splitlines() if any(k in ln for k in got)]
            hits.append((cat, os.path.basename(fp), got, ctx[:3]))

print(f"扫描 {n} 张，命中 {len(hits)} 张")
for cat, fn, got, ctx in hits:
    print(f"- [{cat}] {fn} keys={got}")
    for c in ctx:
        print(f"    | {c}")
