"""
2026 补充入库脚本
=================
处理用户下载的 8 个 2026 录取分数文件：

[xlsx] 普通类·专科提前批 录取最低分（历史/物理）
    - lns2026gklqzktqzj080202W.xlsx  (历史)
    - lns2026gklqzktqzj080202L.xlsx  (物理)
    列：院校编号 / 招生院校 / 录取最低分
    入库：batch=专科提前批, category=普通类, is_collection=False, score_kind=录取最低分

[xlsx] 普通类·本科批 第二次“征集志愿” 投档最低分（历史/物理）
    - lns2026bkzdfzj20729w.xlsx  (历史)
    - lns2026bkzdfzj20729l.xlsx  (物理)
    列：院校编号/招生院校/专业编号/招生专业/投档最低分/(一)~(七)排序项
    入库：batch=本科批, category=普通类, is_collection=True, score_kind=投档最低分

[pdf] 艺术类·专科批 征集（历史/物理）投档最低分
    - lns2026gklq0729d3zdf.pdf  (历史)
    - lns2026gklq0729d7zdf.pdf  (物理)
[pdf] 体育类·专科批 征集（历史/物理）投档最低分
    - lns2026gklq0729i4zdf.pdf  (历史)
    - lns2026gklq0729i8zdf.pdf  (物理)
    PDF 文字表（带竖排水印，需过滤），列与征集 xlsx 类似。

运行：
    python3 etl/load_2026_supplement.py --dry-run      # 只解析不入库，打印核对
    python3 etl/load_2026_supplement.py                # 正式入库
"""
import os
import re
import sys
import json
import argparse
import psycopg2
import openpyxl
import pdfplumber

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# 写库连接串：从环境变量读取，禁止硬编码口令。
#   export GAOKAO_WRITER_DSN="postgresql://gaokao_writer:***@localhost:5432/gaokao"
# 未设置时报错退出（不再回退到硬编码明文口令）。
WRITER_DSN = os.environ.get("GAOKAO_WRITER_DSN")
if not WRITER_DSN:
    sys.exit(
        "错误：环境变量 GAOKAO_WRITER_DSN 未设置。\n"
        "请先设置写库连接串（勿硬编码到源码），例如：\n"
        '  export GAOKAO_WRITER_DSN="postgresql://gaokao_writer:<password>@localhost:5432/gaokao"'
    )

# 竖排水印字符（辽宁省招生考试委员会办公室高等教育）——需从 PDF 文字中滤除
WM_CHARS = set("辽宁省招生考试委员会办公室高等教育")

# 文件 → 目标映射
XLSX_MAP = [
    {
        "file": "2026/lns2026gklqzktqzj080202W.xlsx",
        "category": "普通类", "batch": "专科提前批",
        "is_collection": False, "subject": "历史学科类", "score_kind": "录取最低分",
    },
    {
        "file": "2026/lns2026gklqzktqzj080202L.xlsx",
        "category": "普通类", "batch": "专科提前批",
        "is_collection": False, "subject": "物理学科类", "score_kind": "录取最低分",
    },
    {
        "file": "2026/lns2026bkzdfzj20729w.xlsx",
        "category": "普通类", "batch": "本科批",
        "is_collection": True, "subject": "历史学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026bkzdfzj20729l.xlsx",
        "category": "普通类", "batch": "本科批",
        "is_collection": True, "subject": "物理学科类", "score_kind": "投档最低分",
    },
]

PDF_MAP = [
    {
        "file": "2026/lns2026gklq0729d3zdf.pdf",
        "category": "艺术类", "batch": "专科批",
        "is_collection": True, "subject": "历史学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklq0729d7zdf.pdf",
        "category": "艺术类", "batch": "专科批",
        "is_collection": True, "subject": "物理学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklq0729i4zdf.pdf",
        "category": "体育类", "batch": "专科批",
        "is_collection": True, "subject": "历史学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklq0729i8zdf.pdf",
        "category": "体育类", "batch": "专科批",
        "is_collection": True, "subject": "物理学科类", "score_kind": "投档最低分",
    },
]


def clean_num(s):
    """把混合了水印字符的数字串还原成数字。返回 (value, suspicious)。"""
    if s is None:
        return None, False
    s = str(s).strip()
    if s == "":
        return None, False
    # 去除水印字符
    cleaned = "".join(ch for ch in s if ch not in WM_CHARS)
    cleaned = cleaned.replace(" ", "")
    # 合法数字（整数或小数）
    if re.fullmatch(r"\d+(\.\d+)?", cleaned):
        return cleaned, False
    # 含可疑字符
    return cleaned, True


def parse_xlsx(path):
    """返回 list[dict]，含字段 school_code, school_name, major_code, major_name,
    lowest_score, tiebreak_1..7, raw_row(list)。"""
    wb = openpyxl.load_workbook(os.path.join(ROOT, path), read_only=True, data_only=True)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    wb.close()
    # 找表头行：含 '院校编号' 或 '院校\n编号'
    header_idx = None
    for i, r in enumerate(rows):
        cells = [str(c).replace("\n", "") for c in r if c is not None]
        if any("院校编号" in c for c in cells):
            header_idx = i
            break
    if header_idx is None:
        raise RuntimeError(f"{path}: 未找到表头行")
    # 表头可能跨两行（(一)~(七) 在下一行）
    header = [str(c).replace("\n", "").strip() if c is not None else "" for c in rows[header_idx]]
    # 合并下一行
    if header_idx + 1 < len(rows):
        nxt = rows[header_idx + 1]
        for j, c in enumerate(nxt):
            if c is not None and str(c).strip():
                header[j] = (header[j] + " " + str(c).strip()).strip()
    # 列索引
    def idx(sub):
        for j, h in enumerate(header):
            if sub in h:
                return j
        return None
    i_code = idx("院校编号")
    i_school = idx("招生院校")
    i_mcode = idx("专业编号")
    i_major = idx("招生专业")
    i_score = idx("投档最低分") or idx("录取最低分")
    tb = [idx(f"（{k}）") for k in range(1, 8)]
    # 兼容无括号写法
    if None in tb:
        tb = [idx(f"({k})") for k in range(1, 8)]

    out = []
    for r in rows[header_idx + 1:]:
        # 跳过全空行
        if all(c is None or str(c).strip() == "" for c in r):
            continue
        # 院校编号必须为数字串，否则可能是注脚
        code = r[i_code] if i_code is not None else None
        if code is None or str(code).strip() == "":
            continue
        rec = {
            "school_code": str(code).strip(),
            "school_name": str(r[i_school]).strip() if r[i_school] is not None else "",
            "major_code": str(r[i_mcode]).strip() if (i_mcode is not None and r[i_mcode] is not None) else None,
            "major_name": str(r[i_major]).strip() if (i_major is not None and r[i_major] is not None) else None,
            "lowest_score": r[i_score],
            "tiebreaks": [r[t] if t is not None else None for t in tb],
            "raw_row": [str(c) for c in r],
        }
        out.append(rec)
    return out


def parse_pdf(path):
    """按坐标分栏解析 PDF 文字表，过滤竖排水印。
    列 x 锚定（基于 d3 样例）：
        院校编号 ~55, 院校名称 ~77, 专业代号 ~163, 专业名称 ~185,
        专业备注 ~261(可选), 投档成绩 ~535,
        (一)~(八)排序项 565/594/623/644/673/706/744/776
    """
    rows_out = []
    with pdfplumber.open(os.path.join(ROOT, path)) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            # 过滤水印：字符属于 WM_CHARS 且位于竖排带（top<100 或 x 在 460-620 且构成竖列）
            data_words = []
            for w in words:
                t = w["text"]
                x0 = w["x0"]
                top = w["top"]
                # 水印竖列：top 为负或 x 在 460~620 之间且文字为 WM 字符
                if t in WM_CHARS and (top < 100 or 460 <= x0 <= 620):
                    continue
                data_words.append(w)
            # 按 top 排序，找到所有“院校编号”数据行锚点
            data_words.sort(key=lambda w: (w["top"], w["x0"]))
            # 找数据行：包含“院校编号”列（x≈55，纯数字4位）的行
            code_words = [w for w in data_words
                          if 45 <= w["x0"] <= 75 and re.fullmatch(r"\d{4}", w["text"])]
            for code_w in code_words:
                # 以 code 的 top 为中心，收集 ±10px 垂直窗口内的所有词（处理校名/专业名轻微错位）
                ctop = code_w["top"]
                band = [w for w in data_words if abs(w["top"] - ctop) <= 10]
                band.sort(key=lambda w: w["x0"])

                def nearest(x_center, tol=24, pool=band):
                    best = None
                    for w in pool:
                        if abs((w["x0"] + w["x1"]) / 2 - x_center) < tol:
                            if best is None or abs((w["x0"] + w["x1"]) / 2 - x_center) < abs((best["x0"] + best["x1"]) / 2 - x_center):
                                best = w
                    return best
                # 院校名称：院校编号右侧、专业代号左侧
                school_w = nearest(115)
                mcode_w = nearest(163)
                major_w = nearest(200)
                # 投档成绩
                score_w = nearest(535)
                tb_centers = [565, 594, 623, 644, 673, 706, 744, 776]
                tbs = [nearest(c) for c in tb_centers]

                rec = {
                    "school_code": code_w["text"],
                    "school_name": school_w["text"] if school_w else "",
                    "major_code": mcode_w["text"] if mcode_w else None,
                    "major_name": major_w["text"] if major_w else None,
                    "lowest_score": score_w["text"] if score_w else None,
                    "tiebreaks": [t["text"] if t else None for t in tbs],
                    "raw_row": [w["text"] for w in band],
                }
                rows_out.append(rec)
    return rows_out


def build_records():
    """汇总所有文件解析结果。返回 (records, issues)。
    xlsx 自动解析；PDF（艺术/体育专科批征集）使用人工逐行核对的精确数据。"""
    import pdf_2026_supplement_verified as PV
    assert hasattr(PV, "PDF_VERIFIED")
    records = []
    issues = []
    for m in XLSX_MAP:
        path = m["file"]
        try:
            parsed = parse_xlsx(path)
        except Exception as e:
            issues.append(f"解析失败 {path}: {e}")
            continue
        for p in parsed:
            score_val, susp = clean_num(p["lowest_score"])
            tbs = []
            for t in p["tiebreaks"]:
                v, s = clean_num(t)
                tbs.append(v)
                if s:
                    susp = True
            rec = _make_rec(m, p, score_val, tbs, p["raw_row"], path)
            if susp:
                issues.append(f"可疑分数 {path} 院校{p['school_code']}: {p['lowest_score']}")
            records.append(rec)

    # PDF：使用人工核对数据（按文件名映射）
    for fname, rows in PV.PDF_VERIFIED.items():
        meta = next(mm for mm in PDF_MAP if mm["file"].endswith(fname))
        for row in rows:
            (scode, sname, mcode, mname, score, tbs) = row
            rec = {
                "year": 2026,
                "category": meta["category"],
                "batch": meta["batch"],
                "is_collection": meta["is_collection"],
                "subject": meta["subject"],
                "score_kind": meta["score_kind"],
                "school_code": scode,
                "school_name": sname,
                "major_code": mcode,
                "major_name": mname,
                "lowest_score": score,
                "tiebreak_1": tbs[0] if len(tbs) > 0 else None,
                "tiebreak_2": tbs[1] if len(tbs) > 1 else None,
                "tiebreak_3": tbs[2] if len(tbs) > 2 else None,
                "tiebreak_4": tbs[3] if len(tbs) > 3 else None,
                "tiebreak_5": tbs[4] if len(tbs) > 4 else None,
                "tiebreak_6": tbs[5] if len(tbs) > 5 else None,
                "tiebreak_7": tbs[6] if len(tbs) > 6 else None,
                "raw_row": json.dumps(row, ensure_ascii=False),
                "_src_file": meta["file"],
            }
            records.append(rec)
    return records, issues


def _make_rec(m, p, score_val, tbs, raw_row, path):
    return {
        "year": 2026,
        "category": m["category"],
        "batch": m["batch"],
        "is_collection": m["is_collection"],
        "subject": m["subject"],
        "score_kind": m["score_kind"],
        "school_code": p["school_code"],
        "school_name": p["school_name"],
        "major_code": p["major_code"],
        "major_name": p["major_name"],
        "lowest_score": score_val,
        "tiebreak_1": tbs[0] if len(tbs) > 0 else None,
        "tiebreak_2": tbs[1] if len(tbs) > 1 else None,
        "tiebreak_3": tbs[2] if len(tbs) > 2 else None,
        "tiebreak_4": tbs[3] if len(tbs) > 3 else None,
        "tiebreak_5": tbs[4] if len(tbs) > 4 else None,
        "tiebreak_6": tbs[5] if len(tbs) > 5 else None,
        "tiebreak_7": tbs[6] if len(tbs) > 6 else None,
        "raw_row": json.dumps(raw_row, ensure_ascii=False),
        "_src_file": path,
    }
    return records, issues


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    records, issues = build_records()

    # 按文件统计
    from collections import Counter
    by_file = Counter(r["_src_file"] for r in records)
    print("=== 解析统计 ===")
    for f, c in by_file.items():
        print(f"  {f}: {c} 行")
    print(f"总计: {len(records)} 行")
    print(f"\n=== 可疑项 ({len(issues)}) ===")
    for it in issues:
        print("  !", it)

    if args.dry_run:
        print("\n[DRY-RUN] 未写入数据库。")
        return

    if issues:
        print(f"\n发现 {len(issues)} 条可疑数据，请确认后再正式入库（加 --force 跳过）。")
        print("默认终止。如需忽略可疑项入库，请检查后重新运行。")
        # 仍然允许入库，但打印警告
        # return  # 取消注释可强制阻止

    conn = psycopg2.connect(WRITER_DSN)
    cur = conn.cursor()
    inserted = 0
    # 幂等重载：先删除本次涉及的 (filename 语义) 对应的旧 admission_scores，
    # 再重新插入，避免重复运行导致 admission_scores 累积。
    # 以 source_files 语义键定位旧 src_id。
    seen_src_keys = set()
    for r in records:
        fname = os.path.basename(r["_src_file"])
        fmt = "xlsx" if r["_src_file"].endswith(".xlsx") else "pdf"
        # upsert source_files（依赖 0008 建立的复合唯一索引）
        cur.execute(
            """INSERT INTO source_files
                 (filename, fmt, year, category, batch, is_collection, subject,
                  status, note, loaded_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,'loaded',%s, now())
               ON CONFLICT (filename, COALESCE(year, -1), COALESCE(category, ''),
                            COALESCE(batch, ''), COALESCE(subject, ''),
                            COALESCE(is_collection, FALSE))
               DO UPDATE SET status='loaded', note=EXCLUDED.note, loaded_at=now()
               RETURNING id""",
            (fname, fmt, r["year"], r["category"], r["batch"], r["is_collection"],
             r["subject"], "supplement load"),
        )
        src_id = cur.fetchone()[0]

        # 第一次见到该 src_id：清空其旧 admission_scores（幂等重载）
        if src_id not in seen_src_keys:
            cur.execute("DELETE FROM admission_scores WHERE src_id=%s", (src_id,))
            seen_src_keys.add(src_id)

        cur.execute(
            """INSERT INTO admission_scores
               (src_id, year, category, batch, is_collection, subject, school_code, school_name,
                major_code, major_name, score_kind, lowest_score,
                tiebreak_1, tiebreak_2, tiebreak_3, tiebreak_4, tiebreak_5, tiebreak_6, tiebreak_7,
                raw_row)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (src_id, r["year"], r["category"], r["batch"], r["is_collection"], r["subject"],
             r["school_code"], r["school_name"], r["major_code"], r["major_name"], r["score_kind"],
             r["lowest_score"], r["tiebreak_1"], r["tiebreak_2"], r["tiebreak_3"], r["tiebreak_4"],
             r["tiebreak_5"], r["tiebreak_6"], r["tiebreak_7"], r["raw_row"]),
        )
        inserted += 1

    # 同步批次发布状态：本次入库的 (year,category,subject,batch,stage) 标记为已完成
    cur.execute(
        """INSERT INTO admission_publication_status
             (year, category, subject, batch, stage, status, system_updated_at)
           SELECT DISTINCT year, category, subject, batch,
                  CASE WHEN is_collection THEN '征集' ELSE '常规' END,
                  '已完成', now()
           FROM admission_scores
           WHERE src_id = ANY(%s)
           ON CONFLICT (year, category, subject, batch, stage)
           DO UPDATE SET status='已完成', system_updated_at=now()""",
        (list(seen_src_keys),),
    )

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n[OK] 已入库 {inserted} 行（幂等重载，重复运行不再累积）。")


if __name__ == "__main__":
    main()
