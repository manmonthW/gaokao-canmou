"""以 .md 文件（清洗后的 HTML 表格）为准，核查 2025 目录下 PDF 入库内容是否一致。

两种模式：
  --audit   只读比对：打印每个 pdf 对应 .md 与 admission_scores 的差异报告
  --fix     以 .md 为准重写：删除该 pdf 旧记录，用 .md 解析结果重新入库
            （原始文本 raw_texts 也替换为 .md 纯文本，幂等）

用法：
  python3 md_consistency.py --audit
  python3 md_consistency.py --fix
"""
import os, re, sys, glob, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import psycopg2, psycopg2.extras
from bs4 import BeautifulSoup
from config import BASE_DIR, DSN
import load

YEAR_DIRS = ["2025", "2026"]


def _to_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "—", "无", "None"):
        return None
    s = s.replace(",", "").replace("，", "")
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group()) if m else None


def parse_md(path):
    """解析 .md（含 HTML 表格）为记录列表。返回 (rows, plain_text)。"""
    text = open(path, encoding="utf-8").read()
    soup = BeautifulSoup(text, "html.parser")
    rows = []
    table = soup.find("table")
    if table:
        for tr in table.find_all("tr"):
            tds = tr.find_all("td")
            vals = [td.get_text(strip=True) for td in tds]
            if len(vals) < 9:
                continue
            if not re.match(r"^\d{3,6}$", vals[0]):
                continue
            rows.append(vals)
    # 纯文本（去掉 HTML 标签）
    plain = soup.get_text("\n", strip=True) if soup else text
    return rows, plain


def infer_meta(text, filename):
    cat = "艺术类" if "艺术" in text else ("体育类" if "体育" in text else "普通类")
    subj = ("物理学科类" if "物理学科类" in text
            else "历史学科类" if "历史学科类" in text else None)
    batch = None
    for pat in ["本科提前批A段", "本科提前批B段", "本科提前批",
                "专科批", "本科批", "提前批"]:
        if pat in text:
            batch = pat
            break
    is_coll = "征集" in text
    score_kind = "录取最低分" if "录取最低分" in text else "投档最低分"
    m = re.search(r"20\d{2}", filename)
    year = int(m.group()) if m else None
    return dict(year=year, category=cat, subject=subj, batch=batch,
                is_collection=is_coll, score_kind=score_kind)


def _is_num(v):
    if v is None:
        return False
    s = str(v).strip()
    return s != "" and _to_float(s) is not None


def row_to_record(vals, meta):
    # 前 4 列固定：院校编号 / 院校名称 / 专业代号 / 专业名称
    code = vals[0]
    name = vals[1]
    major_code = vals[2].strip() if len(vals) > 2 and vals[2].strip() != "" else None
    major_name = vals[3].strip() if len(vals) > 3 and vals[3].strip() != "" else None
    # 从右向左取 8 个数值列 = 同分排序项(一)..(八)（最右为 志愿号，丢弃）
    # 其左侧紧邻的数值列 = 投档最低分
    tbs = []
    i = len(vals) - 1
    while len(tbs) < 8 and i >= 0:
        if _is_num(vals[i]):
            tbs.append(vals[i]); i -= 1
        else:
            i -= 1
    tbs = tbs[::-1]  # tb1..tb8（左->右）
    while i >= 0 and not _is_num(vals[i]):
        i -= 1
    lowest = vals[i] if i >= 0 and _is_num(vals[i]) else None
    return {
        "year": meta["year"],
        "category": meta["category"],
        "batch": meta["batch"],
        "is_collection": meta["is_collection"],
        "subject": meta["subject"],
        "school_code": code,
        "school_name": name,
        "major_code": major_code,
        "major_name": major_name,
        "score_kind": meta["score_kind"],
        "lowest_score": _to_float(lowest),
        "tb1": _to_float(tbs[0]) if len(tbs) > 0 else None,
        "tb2": _to_float(tbs[1]) if len(tbs) > 1 else None,
        "tb3": _to_float(tbs[2]) if len(tbs) > 2 else None,
        "tb4": _to_float(tbs[3]) if len(tbs) > 3 else None,
        "tb5": _to_float(tbs[4]) if len(tbs) > 4 else None,
        "tb6": _to_float(tbs[5]) if len(tbs) > 5 else None,
        "tb7": _to_float(tbs[6]) if len(tbs) > 6 else None,
        "raw_row": {"md": vals},
    }


def key_of(rec):
    return (rec.get("school_code"), rec.get("major_code"),
            rec.get("school_name"), rec.get("major_name"))


def _f(x):
    return float(x) if x is not None else None


def load_db(conn, filename):
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM source_files WHERE filename=%s", (filename,))
        row = cur.fetchone()
        if not row:
            return None, []
        sid = row[0]
        cur.execute(
            """SELECT school_code, school_name, major_code, major_name,
                      lowest_score, tiebreak_1, tiebreak_2, tiebreak_3,
                      tiebreak_4, tiebreak_5, tiebreak_6, tiebreak_7
               FROM admission_scores WHERE src_id=%s""", (sid,))
        db = []
        for r in cur.fetchall():
            db.append({
                "school_code": r[0], "school_name": r[1], "major_code": r[2],
                "major_name": r[3], "lowest_score": r[4],
                "tb1": r[5], "tb2": r[6], "tb3": r[7], "tb4": r[8],
                "tb5": r[9], "tb6": r[10], "tb7": r[11],
            })
        return sid, db


def audit(conn):
    total = dict(md=0, db=0, matched=0, missing=0, extra=0, mismatch=0)
    print("=" * 100)
    print(f"{'PDF文件':42} {'md行':>5} {'db行':>5} {'一致':>5} {'缺(在md不在db)':>14} {'多(在db不在md)':>14} {'值不一致':>8}")
    print("=" * 100)
    for d in YEAR_DIRS:
        root = os.path.join(BASE_DIR, d)
        for md in sorted(glob.glob(os.path.join(root, "*.md"))):
            pdf = md[:-3] + ".pdf"
            if not os.path.exists(pdf):
                continue
            filename = os.path.basename(pdf)
            rows, _ = parse_md(md)
            meta = infer_meta(open(md, encoding="utf-8").read(), filename)
            md_recs = [row_to_record(v, meta) for v in rows]
            _, db_recs = load_db(conn, filename)

            md_map = {key_of(r): r for r in md_recs}
            db_map = {key_of(r): r for r in db_recs}
            matched = missing = extra = mismatch = 0
            for k, mr in md_map.items():
                if k not in db_map:
                    missing += 1
                else:
                    dr = db_map[k]
                    same = (_f(mr["lowest_score"]) == _f(dr["lowest_score"])
                            and all(_f(mr[f"tb{i}"]) == _f(dr[f"tb{i}"])
                                    for i in range(1, 8)))
                    if same:
                        matched += 1
                    else:
                        mismatch += 1
            extra = sum(1 for k in db_map if k not in md_map)

            total["md"] += len(md_recs)
            total["db"] += len(db_recs)
            total["matched"] += matched
            total["missing"] += missing
            total["extra"] += extra
            total["mismatch"] += mismatch
            flag = "OK" if (missing == 0 and extra == 0 and mismatch == 0) else "不一致"
            print(f"{filename:42} {len(md_recs):5d} {len(db_recs):5d} {matched:5d} "
                  f"{missing:14d} {extra:14d} {mismatch:8d}  {flag}")
    print("=" * 100)
    print(f"合计: md={total['md']} db={total['db']} 一致={total['matched']} "
          f"缺={total['missing']} 多={total['extra']} 值不一致={total['mismatch']}")
    return total


def fix(conn):
    n_ok = n_skip = 0
    for d in YEAR_DIRS:
        root = os.path.join(BASE_DIR, d)
        for md in sorted(glob.glob(os.path.join(root, "*.md"))):
            pdf = md[:-3] + ".pdf"
            if not os.path.exists(pdf):
                continue
            filename = os.path.basename(pdf)
            text = open(md, encoding="utf-8").read()
            rows, plain = parse_md(md)
            meta = infer_meta(text, filename)
            recs = [row_to_record(v, meta) for v in rows]
            # 按唯一键去重（同一文件内若真有重复行，保留首条）
            seen, dedup, dropped = set(), [], 0
            for r in recs:
                k = (r["school_code"], r["major_code"], r["major_name"],
                     r["subject"], r["score_kind"])
                if k in seen:
                    dropped += 1
                    continue
                seen.add(k)
                dedup.append(r)
            recs = dedup
            load.load_file(conn, filename, "pdf", meta, recs,
                           raw_pages=[(1, plain)])
            print(f"FIX {filename}: md行={len(rows)} 入库={len(recs)} 去重丢弃={dropped} meta={meta}")
            n_ok += 1
    print(f"\n完成：重写 {n_ok} 个 PDF（以 .md 为准）")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audit", action="store_true", help="只读比对")
    ap.add_argument("--fix", action="store_true", help="以md重写入库")
    args = ap.parse_args()
    conn = psycopg2.connect(DSN)
    try:
        if args.fix:
            fix(conn)
        else:
            audit(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
