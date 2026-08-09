# -*- coding: utf-8 -*-
"""探测 保研率 PDF 结构：打印前几页文本与表格抽取样例。"""
import pdfplumber

PATH = "/home/ekewang/projects/gaokao/ln/2026allmaterial/2025高考志愿填报资料汇总/全国367所具有保研资格院校保研率.pdf"

with pdfplumber.open(PATH) as pdf:
    print("total pages:", len(pdf.pages))
    for i, page in enumerate(pdf.pages[:3]):
        print(f"\n===== page {i+1} text =====")
        t = page.extract_text() or ""
        print(t[:1200])
        tables = page.extract_tables()
        print(f"-- tables: {len(tables)}")
        if tables:
            for row in tables[0][:6]:
                print(row)
