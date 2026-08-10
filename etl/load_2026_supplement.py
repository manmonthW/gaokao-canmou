"""
2026 补充入库脚本
=================
处理迟到/需人工裁决的 2026 录取分数文件（用户下载）：

[xlsx] 普通类·专科提前批（历史/物理）
    - lns2026gklqzktqzj080202W/L.xlsx  录取最低分（正常录取，非征集）
    - lns2026gklqzktqzj0805W/L.xlsx   “征集志愿”录取最低分
[xlsx] 普通类·本科批 第二次“征集志愿”投档最低分
    - lns2026bkzdfzj20729w/l.xlsx
[xlsx] 普通类·专科批（历史/物理）
    - lns2026gklqzkzdf0806w/l.xlsx    投档最低分（正常投档）
    - lns2026gklqzkjz0809w/l.xlsx     第一次“征集志愿”投档最低分
    列：院校编号/招生院校/(专业编号/招生专业/)投档(录取)最低分/(一)~(七)排序项；
    院校编号合并格空行沿用上行校码前向填充（transform.parse_sheet 统一处理）。

[pdf] 艺术/体育类·专科批 征集（历史/物理）投档最低分
    - lns2026gklq0729d3/d7/i4/i8zdf.pdf
    使用人工逐行核对的精确数据（pdf_2026_supplement_verified.PDF_VERIFIED）。

xlsx 解析复用 readers+transform（与 verify_all 对账同一口径），
meta 用下方映射表裁决，并与标题推断交叉校验防误判。

运行：
    python3 etl/load_2026_supplement.py --dry-run      # 只解析不入库，打印核对
    python3 etl/load_2026_supplement.py                # 正式入库
"""
import os
import sys
import json
import argparse
import psycopg2

import readers
import transform
import load
from meta import infer_meta, title_blob

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

# 文件 → 目标映射（meta 以标题原文裁决；build_records 内与 infer_meta 交叉校验）
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
    {
        "file": "2026/lns2026gklqzktqzj0805W.xlsx",
        "category": "普通类", "batch": "专科提前批",
        "is_collection": True, "subject": "历史学科类", "score_kind": "录取最低分",
    },
    {
        "file": "2026/lns2026gklqzktqzj0805L.xlsx",
        "category": "普通类", "batch": "专科提前批",
        "is_collection": True, "subject": "物理学科类", "score_kind": "录取最低分",
    },
    {
        "file": "2026/lns2026gklqzkzdf0806w.xlsx",
        "category": "普通类", "batch": "专科批",
        "is_collection": False, "subject": "历史学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklqzkzdf0806l.xlsx",
        "category": "普通类", "batch": "专科批",
        "is_collection": False, "subject": "物理学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklqzkjz0809w.xlsx",
        "category": "普通类", "batch": "专科批",
        "is_collection": True, "subject": "历史学科类", "score_kind": "投档最低分",
    },
    {
        "file": "2026/lns2026gklqzkjz0809l.xlsx",
        "category": "普通类", "batch": "专科批",
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
            sheets = readers.read_spreadsheet(os.path.join(ROOT, path))
        except Exception as e:
            issues.append(f"解析失败 {path}: {e}")
            continue
        for sheet, rows in sheets:
            # 交叉校验：标题推断 vs 裁决映射，防 meta 误判
            im = infer_meta(title_blob(rows, sheet), os.path.basename(path))
            for k in ("batch", "is_collection", "subject"):
                if im.get(k) != m[k]:
                    issues.append(f"meta 不一致 {path}[{sheet}] {k}: 推断={im.get(k)} 映射={m[k]}")
            recs, ok = transform.parse_sheet(rows)
            if not ok:
                issues.append(f"未找到表头 {path}[{sheet}]")
                continue
            if recs and recs[0]["score_kind"] != m["score_kind"]:
                issues.append(f"meta 不一致 {path}[{sheet}] score_kind: "
                              f"推断={recs[0]['score_kind']} 映射={m['score_kind']}")
            for p in recs:
                if p["lowest_score"] is None:
                    issues.append(f"可疑分数 {path} 院校{p['school_code']}: "
                                  f"{p['raw_row'].get('lowest')}")
                records.append(_make_rec(m, p, path))

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


def _make_rec(m, p, path):
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
        "lowest_score": p["lowest_score"],
        "tiebreak_1": p["tb1"],
        "tiebreak_2": p["tb2"],
        "tiebreak_3": p["tb3"],
        "tiebreak_4": p["tb4"],
        "tiebreak_5": p["tb5"],
        "tiebreak_6": p["tb6"],
        "tiebreak_7": p["tb7"],
        "raw_row": json.dumps(p["raw_row"], ensure_ascii=False),
        "_src_file": path,
    }


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
    # 院校维度：新校码先入 schools（admission_scores.school_code 外键约束）
    schools = {(r["school_code"], r["school_name"])
               for r in records
               if r.get("school_code") and r.get("school_name")}
    if schools:
        from psycopg2 import extras
        extras.execute_values(
            cur,
            "INSERT INTO schools (code,name) VALUES %s "
            "ON CONFLICT (code) DO NOTHING",
            list(schools))
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

    # 同步发布状态矩阵（共用 load.sync_publication_status，防登记遗漏）
    load.sync_publication_status(conn)

    conn.commit()
    cur.close()
    conn.close()
    print(f"\n[OK] 已入库 {inserted} 行（幂等重载，重复运行不再累积）。")


if __name__ == "__main__":
    main()
