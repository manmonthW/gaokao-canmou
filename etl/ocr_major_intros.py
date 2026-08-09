#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
解析《普通高等学校本科专业介绍（1936页）》PDF，按专业切分提取，
匹配 major_catalog，入库到 major_hot_profiles（用户确认目标表）。

提取策略：
- 该 PDF 为 Word 导出的 tagged PDF，正文为可选中文本，无需图像级 OCR。
- 使用 PyMuPDF (fitz) 逐页抽取文本，对嵌入字体比 pdftotext 更稳。
- 专业起始判定：『本科/专科/研究生』行的上一行即专业名（中间可能夹一个“XX类”类目行）。
- 表头/字段均按固定标签抽取，标签单独成行，值在其下一行（字段正文跨多行需拼接）。

用法：
  python3 etl/ocr_major_intros.py --dry-run            # 仅解析打印前若干专业，不入裤
  python3 etl/ocr_major_intros.py --load               # 解析并写入数据库
  python3 etl/ocr_major_intros.py --load --limit 50
"""
import os
import re
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import DSN  # noqa: E402

PDF_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "2026allmaterial", "2025高考志愿填报资料汇总",
    "普通高等学校本科专业介绍（1936页）.pdf",
)

# 表头标签 -> (列名)  —— 值在前、标签在后，遇到标签时把 last_value 赋给该列
# 注：学历层次 的“值”即本科/专科行本身（已在触发新专业时存入 level_raw），此处不重复映射
HEADER_LABELS = {
    "修业年限": "length_raw",
    "授予学位": "degree",
    "文理比例": "arts_science_ratio",
    "男女比例": "gender_ratio",
}
# 字段标签 -> 列名
FIELD_LABELS = {
    "专业简介": "introduction",
    "培养目标": "training_goal",
    "培养要求": "training_req",
    "学科要求": "discipline_req",
    "知识能力": "knowledge_ability",
    "考研方向": "postgrad_dir",
    "主要课程": "main_courses",
    "就业方向": "employment_dir",
    "社会名人": "social_celebrities",
}
ALT_INTRO_LABEL = "专业介绍"
LEVEL_WORDS = {"本科", "专科", "研究生"}
# 章节/区段伪标题（出现“XX类”之后的非专业标题），解析时跳过
SECTION_HEADERS = {"开设院校", "专业代码", "相近专业", "职业去向", "考研导读"}


def extract_text():
    import fitz
    doc = fitz.open(PDF_PATH)
    pages = [page.get_text("text") for page in doc]
    doc.close()
    return pages


def clean_line(s):
    s = s.replace("\u3000", " ").replace("\xa0", " ").strip()
    return s


def blank_major(name):
    return {
        "name": name, "level_raw": "", "length_raw": "", "degree": "",
        "arts_science_ratio": "", "gender_ratio": "",
        "introduction": "", "training_goal": "", "training_req": "",
        "discipline_req": "", "knowledge_ability": "",
        "postgrad_dir": "", "main_courses": "", "employment_dir": "",
        "social_celebrities": "",
    }


def parse_majors(pages):
    lines = [clean_line(ln) for p in pages for ln in p.splitlines()]
    lines = [ln for ln in lines if ln != ""]

    majors = []
    cur = None
    pending_label = None      # (kind, col)  kind in {header, field}
    pending_buf = []
    last_value = ""           # 最近一条非标签文本行（用于“值在前、标签在后”的表头）

    def flush_pop_name(name):
        # 新专业起始前，若上一行专业名被误并入上一专业的字段缓冲，则弹出
        nonlocal pending_buf
        if pending_buf and pending_buf[-1] == name:
            pending_buf.pop()

    def flush():
        nonlocal pending_label, pending_buf
        if pending_label is not None and cur is not None:
            text = "".join(pending_buf).strip()
            kind, col = pending_label
            if kind == "field":
                if col == "introduction" and cur.get("introduction"):
                    pass
                else:
                    cur[col] = text
            else:  # header：值已在 last_value
                cur[col] = last_value
        pending_label = None
        pending_buf = []

    i, n = 0, len(lines)
    while i < n:
        ln = lines[i]
        # 触发新专业：本科/专科/研究生 行的上一行是专业名（中间可能夹“XX类”类目行）
        if ln in LEVEL_WORDS:
            # 取专业名（上一行；若上一行是“XX类”则取再上一行）
            name = lines[i - 1] if i - 1 >= 0 else ""
            if name.endswith("类") and i - 2 >= 0:
                name = lines[i - 2]
            # 过滤章节/区段伪标题（如“开设院校”等）
            if name in SECTION_HEADERS or name.endswith("院校") or len(name) > 15:
                # 不是真正专业，丢弃当前缓冲并跳过
                cur = None
                pending_label = None
                pending_buf = []
                last_value = ""
                i += 1
                continue
            flush_pop_name(name)
            flush()
            if cur is not None:
                majors.append(cur)
            cur = blank_major(name)
            cur["level_raw"] = ln
            # 立即落定已收集的表头值（学历层次/修业年限/授予学位/文理比例/男女比例）
            # 这些值在对应标签之前已存入 last_value，下面遇到标签再赋值
            pending_label = None
            pending_buf = []
            last_value = ""
            i += 1
            continue
        if cur is None:
            i += 1
            continue
        if ln in HEADER_LABELS:
            # 表头为“值在前、标签在后”：把上一条文本行 last_value 赋给该标签列
            col = HEADER_LABELS[ln]
            cur[col] = last_value
            last_value = ""
            i += 1
            continue
        if ln in FIELD_LABELS:
            flush()
            pending_label = ("field", FIELD_LABELS[ln])
            i += 1
            continue
        if ln == ALT_INTRO_LABEL:
            if i + 1 < n and lines[i + 1] == "专业简介":
                flush()
                pending_label = ("field", "introduction")
                i += 2
                continue
            flush()
            pending_label = ("field", "introduction")
            i += 1
            continue
        # 普通文本行：若是字段值则并入缓冲；同时记录为 last_value 供表头标签取值
        if pending_label is not None:
            pending_buf.append(ln)
        last_value = ln
        i += 1
    flush()
    if cur is not None:
        majors.append(cur)
    return majors


def norm_name(s):
    return re.sub(r"\s+", "", s or "").strip()


# 中文数字 -> 阿拉伯数字（仅处理 二~五，覆盖本科修业年限）
_CN_NUM = {"一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def parse_length(raw):
    if not raw:
        return None
    m = re.search(r"(\d+)\s*年", raw)
    if m:
        return int(m.group(1))
    m = re.search(r"([一二两三四五六七八九])\s*年", raw)
    if m:
        return _CN_NUM.get(m.group(1))
    return None


def clean_ratio(s):
    if not s:
        return ""
    s = s.strip()
    # 个别专业无文理/男女比例，PDF 写作 “-:100%”，归一为 “0:100%”
    s = re.sub(r"(?<=^)-:", "0:", s)
    s = re.sub(r":-", ":0", s)
    return s


def load_to_db(majors, limit=None):
    import psycopg2
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    for a in [
        "ALTER TABLE major_hot_profiles ADD COLUMN IF NOT EXISTS training_req text",
        "ALTER TABLE major_hot_profiles ADD COLUMN IF NOT EXISTS knowledge_ability text",
        "ALTER TABLE major_hot_profiles ADD COLUMN IF NOT EXISTS social_celebrities text",
        "ALTER TABLE major_hot_profiles ADD COLUMN IF NOT EXISTS arts_science_ratio text",
        "ALTER TABLE major_hot_profiles ADD COLUMN IF NOT EXISTS level_raw text",
    ]:
        cur.execute(a)
    conn.commit()

    cur.execute("SELECT name, code FROM major_catalog")
    cat = {norm_name(r[0]): r[1] for r in cur.fetchall()}
    cur.execute("SELECT name FROM major_hot_profiles")
    existing = {norm_name(r[0]) for r in cur.fetchall()}
    cur.execute("SELECT COALESCE(MAX(seq),0) FROM major_hot_profiles")
    seq = cur.fetchone()[0]

    inserted = updated = 0
    unmatched = []
    seen = set()
    rows = majors if limit is None else majors[:limit]
    for m in rows:
        nm = norm_name(m["name"])
        if not nm or nm in seen:
            continue
        seen.add(nm)
        code = cat.get(nm)
        if code is None:
            unmatched.append(m["name"])
            continue
        length_val = parse_length(m["length_raw"])
        gender_ratio = clean_ratio(m["gender_ratio"])
        arts_ratio = clean_ratio(m["arts_science_ratio"])
        if nm in existing:
            cur.execute(
                """UPDATE major_hot_profiles SET
                    degree=COALESCE(NULLIF(%s,''),degree),
                    length=COALESCE(%s,length),
                    gender_ratio=COALESCE(NULLIF(%s,''),gender_ratio),
                    introduction=COALESCE(NULLIF(%s,''),introduction),
                    training_goal=COALESCE(NULLIF(%s,''),training_goal),
                    discipline_req=COALESCE(NULLIF(%s,''),discipline_req),
                    main_courses=COALESCE(NULLIF(%s,''),main_courses),
                    postgrad_dir=COALESCE(NULLIF(%s,''),postgrad_dir),
                    employment_dir=COALESCE(NULLIF(%s,''),employment_dir),
                    training_req=COALESCE(NULLIF(%s,''),training_req),
                    knowledge_ability=COALESCE(NULLIF(%s,''),knowledge_ability),
                    social_celebrities=COALESCE(NULLIF(%s,''),social_celebrities),
                    arts_science_ratio=COALESCE(NULLIF(%s,''),arts_science_ratio),
                    level_raw=COALESCE(NULLIF(%s,''),level_raw)
                WHERE name=%s""",
                (m["degree"], length_val, gender_ratio, m["introduction"],
                 m["training_goal"], m["discipline_req"], m["main_courses"],
                 m["postgrad_dir"], m["employment_dir"], m["training_req"],
                 m["knowledge_ability"], m["social_celebrities"],
                 arts_ratio, m["level_raw"], m["name"]),
            )
            updated += 1
        else:
            seq += 1
            cur.execute(
                """INSERT INTO major_hot_profiles
                (code,name,seq,degree,length,gender_ratio,introduction,training_goal,
                 discipline_req,main_courses,postgrad_dir,employment_dir,training_req,
                 knowledge_ability,social_celebrities,arts_science_ratio,level_raw)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (code, m["name"], seq, m["degree"] or None, length_val,
                 gender_ratio or None, m["introduction"] or None,
                 m["training_goal"] or None, m["discipline_req"] or None,
                 m["main_courses"] or None, m["postgrad_dir"] or None,
                 m["employment_dir"] or None, m["training_req"] or None,
                 m["knowledge_ability"] or None, m["social_celebrities"] or None,
                 arts_ratio or None, m["level_raw"] or None),
            )
            inserted += 1
    conn.commit()
    cur.close()
    conn.close()
    return inserted, updated, unmatched


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--load", action="store_true")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    print("提取 PDF 文本 ...", file=sys.stderr)
    pages = extract_text()
    print(f"  共 {len(pages)} 页", file=sys.stderr)
    majors = parse_majors(pages)
    print(f"解析到专业数: {len(majors)}", file=sys.stderr)

    if args.dry_run or not args.load:
        lim = args.limit or 3
        for m in majors[:lim]:
            print("=" * 40)
            print("专业:", m["name"], "| 层次:", m["level_raw"], "| 学制:", m["length_raw"],
                  "| 学位:", m["degree"], "| 文理:", m["arts_science_ratio"],
                  "| 男女:", m["gender_ratio"])
            for k in ("introduction", "training_goal", "training_req",
                      "discipline_req", "knowledge_ability", "postgrad_dir",
                      "main_courses", "employment_dir", "social_celebrities"):
                v = m[k]
                if v:
                    print(f"  [{k}] {v[:70]}{'...' if len(v) > 70 else ''}")
        print("\n（加 --load 写入数据库）", file=sys.stderr)
        return

    inserted, updated, unmatched = load_to_db(majors, args.limit)
    print(f"插入: {inserted}, 更新(回填): {updated}, 未匹配catalog: {len(unmatched)}")
    if unmatched:
        print("未匹配专业(前60):", unmatched[:60])


if __name__ == "__main__":
    main()
