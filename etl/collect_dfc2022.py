#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_dfc2022.py —— 双一流建设学科第二轮（2022）采集解析

来源：教育部 教研函〔2022〕1号
  政策页 http://www.moe.gov.cn/srcsite/A22/s7065/202202/t20220211_598710.html
  附件1  major/dfc2022/W020220214318455516037.pdf（名单本体）
原始存档：major/dfc2022/（不入 git 之外的原始文件区）
产出：etl/data/dfc2022.csv，列 school_name, discipline_name, note
口径：北京大学/清华大学为「自主确定建设学科并自行公布」，
  其学科不按名单展开，以单行 note 标注；147 校 331 学科可人工核对。

用法：python3 etl/collect_dfc2022.py
"""
import csv
import re

import pdfplumber

PDF = "/home/ekewang/projects/gaokao/ln/major/dfc2022/W020220214318455516037.pdf"
OUT = "/home/ekewang/projects/gaokao/ln/etl/data/dfc2022.csv"


def read_text():
    """抽取全部页面文本并按行返回。"""
    lines = []
    with pdfplumber.open(PDF) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                ln = ln.strip()
                if ln:
                    lines.append(ln)
    return lines


def main():
    lines = read_text()
    # 跳过页眉（附件 1 / 标题 / 排序说明），自第一所院校行开始
    rows = []
    buf_name, buf_disc = None, []

    def flush():
        if buf_name is None:
            return
        if buf_name in ("北京大学", "清华大学"):
            rows.append((buf_name, "", "自主确定建设学科并自行公布"))
            return
        discs = re.split(r"[、，]\s*", "".join(buf_disc))
        discs = [d.strip() for d in discs if d.strip()]
        for d in discs:
            rows.append((buf_name, d, ""))

    for ln in lines:
        if ln.startswith(("附件", "第二轮", "（按学校代码排序）")):
            continue
        m = re.match(r"^(\S{2,20}?)：(.*)$", ln)
        if m:
            flush()
            buf_name = m.group(1).strip()
            buf_disc = [m.group(2).strip()]
        elif buf_name is not None:
            buf_disc.append(ln)
    flush()

    schools = {r[0] for r in rows}
    n_disc = sum(1 for r in rows if r[1])
    print(f"[解析] 院校 {len(schools)} 所；学科行 {n_disc} 条（含自主确定 2 行）")

    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["school_name", "discipline_name", "note"])
        w.writerows(rows)
    print(f"[写出] {OUT} 共 {len(rows)} 行（不含表头）")
    for r in rows[:3]:
        print(" 样例:", r)


if __name__ == "__main__":
    main()
