#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_baoyan_rate.py —— 保研率数值灌库（migration 0013）

来源：2026allmaterial/2025高考志愿填报资料汇总/全国367所具有保研资格院校保研率.pdf
口径：取最新年（2021 推免率）百分比，写入 school_profiles.postgrad_recommend_rate。

行解析：PDF 文本行形如「2 浙江工业大学 12.30% 12.30% 10.00%」，
  序号 + 校名 + 若干百分比；取第一个百分比为最新年保研率。
名称对齐：OCR/排版噪声（如「宁波大学克」）先精确匹配 schools.name，
  失败则取最长前缀匹配（≥5 字），仍失败则列入未匹配清单供人工复核。

用法：
  python3 etl/load_baoyan_rate.py            # 灌库
  python3 etl/load_baoyan_rate.py --dry-run  # 只解析打印不写库
"""
import argparse
import re

import pdfplumber
import psycopg2

PATH = "/home/ekewang/projects/gaokao/ln/2026allmaterial/2025高考志愿填报资料汇总/全国367所具有保研资格院校保研率.pdf"
DB = dict(host="localhost", port=5432, dbname="gaokao", user="gaokao", password="gaokao123")

# 行形如：1 浙江大学 25.70% 25.90% 27.30%（校名内无空格；允许百分比内有空格噪声如 9. 2%）
_LINE = re.compile(r"^(\d{1,3})\s+(\S+?)\s+(\d{1,2}(?:\.\s*\d+)?)\s*%")
_SKIP = ("序号", "学校名称", "注：", "公示不全")

# 人工核验的更名/噪声别名（PDF 为 2021 口径旧名，库为 2026 名单新名；
# 保留当年口径率值，仅供横向参考）
_ALIASES = {
    "宁波大学克": "宁波大学",            # 尾部 OCR 噪声字
    "上海对外贸易大学": "上海对外经贸大学",
    "上海体育学院": "上海体育大学",        # 2023 更名
    "蚌埠医学院": "蚌埠医科大学",          # 2023 更名
    "河北中医医院": "河北中医药大学",      # 2023 更名
    "河南水利水电大学": "华北水利水电大学",  # OCR 混淆
    "华北电力大学（保定)": "华北电力大学(保定)",  # 全/半角括号混用
}


def parse_rows():
    """返回 [(ocr_name, rate_float), ...]，rate 为最新年百分比数值。"""
    out = []
    with pdfplumber.open(PATH) as pdf:
        for page in pdf.pages:
            for ln in (page.extract_text() or "").splitlines():
                ln = ln.strip()
                if any(k in ln for k in _SKIP):
                    continue
                m = _LINE.match(ln)
                if not m:
                    continue
                name = m.group(2).strip()
                rate = float(re.sub(r"\s+", "", m.group(3)))
                if not (0 < rate <= 100) or len(name) < 3:
                    continue
                out.append((name, rate))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    rows = parse_rows()
    print(f"[解析] 提取到 {len(rows)} 行（含重复校名以最后一次为准）")
    data = {}
    for name, rate in rows:
        data[name] = rate  # 同校跨页续行时取后出现者

    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT code, name FROM schools")
    name2code = {n: c for c, n in cur.fetchall()}
    all_names = sorted(name2code.keys(), key=len, reverse=True)

    matched, unmatched = {}, []
    for ocr_name, rate in data.items():
        clean = _ALIASES.get(ocr_name) or ocr_name.replace("　", "").strip()
        if clean in name2code:
            matched[name2code[clean]] = (clean, rate)
            continue
        # 最长前缀匹配（容忍尾部 ≤3 字 OCR 噪声）：院校名 ≥4 字且为 OCR 名前缀，
        # 按名称长度降序遍历，优先命中最完整的院校名
        hit = next((n for n in all_names
                    if len(n) >= 4 and clean.startswith(n) and len(clean) - len(n) <= 3), None)
        if hit:
            matched[name2code[hit]] = (f"{ocr_name}→{hit}", rate)
        else:
            unmatched.append((ocr_name, rate))

    print(f"[匹配] 命中 {len(matched)} 所；未匹配 {len(unmatched)} 行")
    for n, r in unmatched:
        print(f"  未匹配: {n} {r}%")

    if args.dry_run:
        print("[dry-run] 不写库")
        return

    # 幂等：先全清再写入，确保 PDF 未收录院校不残留旧率值
    cur.execute("UPDATE school_profiles SET postgrad_recommend_rate=NULL")
    for code, (disp, rate) in matched.items():
        cur.execute(
            """UPDATE school_profiles
               SET postgrad_recommend_rate=%s,
                   has_postgrad_recommend=COALESCE(has_postgrad_recommend, FALSE) OR TRUE
               WHERE code=%s""", (rate, code))
    conn.commit()
    cur.execute("SELECT count(*) FROM school_profiles WHERE postgrad_recommend_rate IS NOT NULL")
    print(f"[写入] postgrad_recommend_rate 非空 {cur.fetchone()[0]} 所")
    cur.execute("""SELECT count(*) FROM school_profiles
                   WHERE has_postgrad_recommend=TRUE AND postgrad_recommend_rate IS NULL""")
    print(f"[报告] 有保研资格但无率值 {cur.fetchone()[0]} 所（PDF 未收录其率）")
    conn.close()


if __name__ == "__main__":
    main()
