#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_eval4.py —— 第四轮学科评估官方全量（2017）采集解析

来源说明：官方页 https://www.cdgdc.edu.cn/dslxkpgjggb/ 当前被 WAF 拦截
  （HTTP 412，含 JS 质询），且 Wayback Machine 存档同样被 WAF 页面污染。
实际来源：学术桥（acabridge.cn）转载的教育部学位中心第四轮学科评估结果
  查询页内嵌数据集 https://www.acabridge.cn/acabridge/aca_web/xkpg4/data.js
  （页面标注「数据请以教育部学位与研究生教育发展中心官方公布为准」）。
交叉核验：GitHub Johnnydaszhu/2017ChinaUniversityDisciplineAssessment 的
  2017教育部第四轮学科评估.csv（若可下载）。
原始存档：major/eval4/（acabridge_data.js 等）
产出：etl/data/eval4_official.csv，列 discipline_code, discipline_name, school_name, grade

用法：python3 etl/collect_eval4.py            # 重新下载并解析
      python3 etl/collect_eval4.py --offline  # 仅用已存档文件解析
"""
import argparse
import csv
import json
import re
import time

import requests

BASE = "https://www.acabridge.cn/acabridge/aca_web/xkpg4/"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36")
ROOT = "/home/ekewang/projects/gaokao/ln"
DATA_JS = f"{ROOT}/major/eval4/acabridge_data.js"
OUT = f"{ROOT}/etl/data/eval4_official.csv"
GRADES = {1: "A+", 2: "A", 3: "A-", 4: "B+", 5: "B",
          6: "B-", 7: "C+", 8: "C", 9: "C-"}

# 已知缺口补丁（经 GitHub CSV 交叉核验后人工确认）：
# 1) acabridge 的 schoolname 字典缺序号 292（单位代码 10289 江苏科技大学），
#    但 data 数组中其 9 条记录齐全，档位取自 data 数组本身，校名经 GitHub 核对。
PATCH_JUST = [
    ("0710", "生物学", "江苏科技大学", "C-"),
    ("0802", "机械工程", "江苏科技大学", "C-"),
    ("0805", "材料科学与工程", "江苏科技大学", "B-"),
    ("0811", "控制科学与工程", "江苏科技大学", "C"),
    ("0812", "计算机科学与技术", "江苏科技大学", "C-"),
    ("0824", "船舶与海洋工程", "江苏科技大学", "C"),
    ("0835", "软件工程", "江苏科技大学", "C-"),
    ("1201", "管理科学与工程", "江苏科技大学", "B-"),
    ("1202", "工商管理", "江苏科技大学", "C"),
]
# 2) acabridge 的 sa2 学科字典漏 0837 安全科学与工程（官方 95 学科之一），
#    该学科 36 条结果取自 GitHub CSV（与官方公布一致）。
PATCH_0837 = [
    ("0837", "安全科学与工程", "中国矿业大学", "A+"),
    ("0837", "安全科学与工程", "中国科学技术大学", "A+"),
    ("0837", "安全科学与工程", "中南大学", "A-"),
    ("0837", "安全科学与工程", "河南理工大学", "A-"),
    ("0837", "安全科学与工程", "西安科技大学", "A-"),
    ("0837", "安全科学与工程", "中国石油大学", "B+"),
    ("0837", "安全科学与工程", "北京理工大学", "B+"),
    ("0837", "安全科学与工程", "北京科技大学", "B+"),
    ("0837", "安全科学与工程", "南京工业大学", "B+"),
    ("0837", "安全科学与工程", "清华大学", "B+"),
    ("0837", "安全科学与工程", "中国地质大学", "B"),
    ("0837", "安全科学与工程", "安徽理工大学", "B"),
    ("0837", "安全科学与工程", "山东科技大学", "B"),
    ("0837", "安全科学与工程", "辽宁工程技术大学", "B"),
    ("0837", "安全科学与工程", "重庆大学", "B"),
    ("0837", "安全科学与工程", "东北大学", "B-"),
    ("0837", "安全科学与工程", "北京交通大学", "B-"),
    ("0837", "安全科学与工程", "太原理工大学", "B-"),
    ("0837", "安全科学与工程", "武汉理工大学", "B-"),
    ("0837", "安全科学与工程", "武汉科技大学", "B-"),
    ("0837", "安全科学与工程", "中国民航大学", "C+"),
    ("0837", "安全科学与工程", "北京化工大学", "C+"),
    ("0837", "安全科学与工程", "南京理工大学", "C+"),
    ("0837", "安全科学与工程", "南华大学", "C+"),
    ("0837", "安全科学与工程", "华南理工大学", "C+"),
    ("0837", "安全科学与工程", "湖南科技大学", "C+"),
    ("0837", "安全科学与工程", "中北大学", "C"),
    ("0837", "安全科学与工程", "华东理工大学", "C"),
    ("0837", "安全科学与工程", "大连理工大学", "C"),
    ("0837", "安全科学与工程", "沈阳航空航天大学", "C"),
    ("0837", "安全科学与工程", "黑龙江科技大学", "C"),
    ("0837", "安全科学与工程", "常州大学", "C-"),
    ("0837", "安全科学与工程", "昆明理工大学", "C-"),
    ("0837", "安全科学与工程", "辽宁石油化工大学", "C-"),
    ("0837", "安全科学与工程", "郑州大学", "C-"),
    ("0837", "安全科学与工程", "青岛科技大学", "C-"),
]


def fetch(path):
    r = requests.get(BASE + path, headers={"User-Agent": UA}, timeout=60)
    r.raise_for_status()
    return r.text


def load_js(text):
    """从 data.js 抽取 sa2（学科代码→名）、schoolname（序号→校名）、data 数组。"""
    m = re.search(r"sa2=(\{.*?\});", text, re.S)
    sub2name = json.loads(m.group(1))          # "s0101": "哲学"
    m = re.search(r"schoolname=(\{.*?\});", text, re.S)
    idx2school = json.loads(m.group(1))        # "0": "北京大学"
    m = re.search(r"data=(\[.*?\]);", text, re.S)
    raw = m.group(1)
    # {s:'0101',l:'1',c:'10001',n:'0',p:'11'} → JSON
    raw = re.sub(r"(\w):'", r'"\1":"', raw)
    raw = raw.replace("'", '"')
    rows = json.loads(raw)
    return sub2name, idx2school, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args()

    if not args.offline:
        for src, dst in [("data.js?new", DATA_JS),
                         ("db.js?new", f"{ROOT}/major/eval4/acabridge_db.js"),
                         ("index.html", f"{ROOT}/major/eval4/acabridge_index.html")]:
            body = fetch(src)
            with open(dst, "w", encoding="utf-8") as f:
                f.write(body)
            print(f"[存档] {dst} ({len(body)} chars)")
            time.sleep(1.2)

    text = open(DATA_JS, encoding="utf-8").read()
    sub2name, idx2school, rows = load_js(text)
    print(f"[解析] 学科 {len(sub2name)} 个；院校 {len(idx2school)} 所；记录 {len(rows)} 条")

    out = []
    seen = set()
    for r in rows:
        code = r["s"]
        name = sub2name.get("s" + code)
        if name is None:
            print(f"  !! 未知学科代码 {code}")
            continue
        school = idx2school.get(r["n"])
        grade = GRADES.get(int(r["l"]))
        if school is None or grade is None:
            print(f"  !! 异常记录 {r}")
            continue
        key = (code, school)
        if key in seen:
            print(f"  !! 重复 {code} {school}")
            continue
        seen.add(key)
        out.append((code, name, school, grade))

    # 应用人工核验补丁（见文件头 PATCH_* 注释）
    for p in PATCH_JUST + PATCH_0837:
        key = (p[0], p[2])
        if key in seen:
            print(f"  !! 补丁已存在，跳过 {p}")
            continue
        seen.add(key)
        out.append(p)
    print(f"[补丁] 江苏科技大学 {len(PATCH_JUST)} 条 + 0837 安全科学与工程 {len(PATCH_0837)} 条")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["discipline_code", "discipline_name", "school_name", "grade"])
        w.writerows(out)
    print(f"[写出] {OUT} 共 {len(out)} 行（不含表头）")
    for r in out[:3]:
        print(" 样例:", r)
    # 分档计数（供人工核对九档分布）
    from collections import Counter
    print("[核对] 分档:", dict(sorted(Counter(r[3] for r in out).items())))


if __name__ == "__main__":
    main()
