"""全量只读校验：重新解析 2025/2026 目录下所有 pdf/xlsx/xls 文件，
与数据库 admission_scores 逐文件比对，确认 DB 与源文件一致。

PDF   -> 以 .md 为基准（复用 md_consistency 的解析逻辑）
XLSX/XLS -> 复用 run.py 的 readers.read_spreadsheet + transform.parse_sheet + meta.infer_meta

用法：
  python3 verify_all.py
"""
import os, sys, glob, importlib.util
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2
from config import BASE_DIR, DSN, DATA_DIRS
import readers, transform
from meta import infer_meta, title_blob

# 复用 md_consistency 的 PDF 解析
spec = importlib.util.spec_from_file_location(
    "md_consistency", os.path.join(os.path.dirname(__file__), "md_consistency.py"))
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)


def _f(x):
    return float(x) if x is not None else None


def key_of(r):
    return (r.get("school_code"), r.get("major_code"),
            r.get("major_name"), r.get("subject"), r.get("score_kind"))


def parse_pdf_md(path):
    md = path[:-4] + ".md"
    if not os.path.exists(md):
        return None
    filename = os.path.basename(path)
    rows, _ = mc.parse_md(md)
    meta = mc.infer_meta(open(md, encoding="utf-8").read(), filename)
    return [mc.row_to_record(v, meta) for v in rows]


def parse_xlsx(path):
    """复刻 run.py 对 xlsx/xls 的解析流程。"""
    filename = os.path.basename(path)
    try:
        sheets = readers.read_spreadsheet(path)
    except readers.EncryptedFile:
        return None  # 加密，跳过
    all_recs = []
    for sheet, rows in sheets:
        blob = title_blob(rows, sheet)
        meta = infer_meta(blob, filename)
        meta["sheet"] = sheet
        recs, ok = transform.parse_sheet(rows)
        for r in recs:
            r.update({k: meta.get(k) for k in
                      ("year", "category", "batch", "is_collection", "subject")})
        all_recs += recs
    return all_recs


def load_db(conn, filename):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_files WHERE filename=%s", (filename,))
        row = cur.fetchone()
        if not row:
            return None, []
        sid = row[0]
        cur.execute(
            """SELECT school_code, school_name, major_code, major_name, subject,
                      score_kind, lowest_score, tiebreak_1, tiebreak_2, tiebreak_3,
                      tiebreak_4, tiebreak_5, tiebreak_6, tiebreak_7,
                      year, category, batch, is_collection
               FROM admission_scores WHERE src_id=%s""", (sid,))
        db = []
        for r in cur.fetchall():
            db.append({
                "school_code": r[0], "school_name": r[1], "major_code": r[2],
                "major_name": r[3], "subject": r[4], "score_kind": r[5],
                "lowest_score": r[6], "tb1": r[7], "tb2": r[8], "tb3": r[9],
                "tb4": r[10], "tb5": r[11], "tb6": r[12], "tb7": r[13],
                "year": r[14], "category": r[15], "batch": r[16],
                "is_collection": r[17],
            })
        return sid, db


def rep_records(path):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        return parse_pdf_md(path)
    elif ext in (".xlsx", ".xls"):
        return parse_xlsx(path)
    return None


def compare(rep, db):
    rep_map = {key_of(r): r for r in rep}
    db_map = {key_of(r): r for r in db}
    matched = missing = extra = mismatch = 0
    mism_examples = []
    for k, mr in rep_map.items():
        if k not in db_map:
            missing += 1
        else:
            dr = db_map[k]
            ok = (_f(mr["lowest_score"]) == _f(dr["lowest_score"])
                  and all(_f(mr[f"tb{i}"]) == _f(dr[f"tb{i}"]) for i in range(1, 8))
                  and mr.get("school_name") == dr.get("school_name")
                  and mr.get("year") == dr.get("year")
                  and mr.get("category") == dr.get("category")
                  and mr.get("batch") == dr.get("batch")
                  and bool(mr.get("is_collection")) == bool(dr.get("is_collection")))
            if ok:
                matched += 1
            else:
                mismatch += 1
                if len(mism_examples) < 3:
                    mism_examples.append((mr, dr))
    extra = sum(1 for k in db_map if k not in rep_map)
    return matched, missing, extra, mismatch, mism_examples


def main():
    conn = psycopg2.connect(DSN)
    totals = dict(rep=0, db=0, matched=0, missing=0, extra=0, mismatch=0, skip=0)
    print("=" * 110)
    print(f"{'文件':46} {'fmt':4} {'rep行':>6} {'db行':>6} {'一致':>5} {'缺':>5} {'多':>5} {'值不一致':>8}  结论")
    print("=" * 110)
    try:
        for d in sorted(DATA_DIRS):
            root = os.path.join(BASE_DIR, d)
            for path in sorted(glob.glob(os.path.join(root, "*"))):
                if os.path.basename(path).startswith("~$"):
                    continue
                ext = os.path.splitext(path)[1].lower()
                if ext not in (".pdf", ".xlsx", ".xls"):
                    continue
                filename = os.path.basename(path)
                rep = rep_records(path)
                if rep is None:
                    print(f"{filename:46} {ext[1:]:4} {'-':>6} {'-':>6} {'-':>5} {'-':>5} {'-':>5} {'-':>8}  跳过(加密/无md)")
                    totals["skip"] += 1
                    continue
                _, db = load_db(conn, filename)
                if db is None:
                    print(f"{filename:46} {ext[1:]:4} {len(rep):6d} {'未入库':>6}  文件未在DB")
                    totals["missing"] += 1
                    continue
                matched, missing, extra, mismatch, ex = compare(rep, db)
                totals["rep"] += len(rep)
                totals["db"] += len(db)
                totals["matched"] += matched
                totals["missing"] += missing
                totals["extra"] += extra
                totals["mismatch"] += mismatch
                flag = "OK" if (missing == 0 and extra == 0 and mismatch == 0) else "不一致"
                print(f"{filename:46} {ext[1:]:4} {len(rep):6d} {len(db):6d} "
                      f"{matched:5d} {missing:5d} {extra:5d} {mismatch:8d}  {flag}")
                for mr, dr in ex:
                    print(f"     值不一致示例 key={key_of(mr)}")
                    print(f"        rep: 最低={mr['lowest_score']} tb={[mr[f'tb{i}'] for i in range(1,8)]} name={mr.get('school_name')}")
                    print(f"        db : 最低={dr['lowest_score']} tb={[dr[f'tb{i}'] for i in range(1,8)]} name={dr.get('school_name')}")
    finally:
        conn.close()
    print("=" * 110)
    print(f"合计: rep={totals['rep']} db={totals['db']} 一致={totals['matched']} "
          f"缺={totals['missing']} 多={totals['extra']} 值不一致={totals['mismatch']} 跳过={totals['skip']}")


if __name__ == "__main__":
    main()
