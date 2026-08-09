#!/usr/bin/env python3
"""解析辽宁高考「成绩统计表(一分一段表)」文字版 PDF -> 结构化行。

12 张 PDF 来源：沈阳本地宝(bendibao) 镜像辽宁招生考试之窗官方发布，
为干净的文字版 PDF（非扫描图），可用 pdfplumber 直接解析。

每张 PDF 4 栏，每栏 "分数 人数 累计"。含一个竖排水印（中文单字），
需按内容过滤。本脚本只解析、校验、打印，不直接落库。
"""
import os, re, glob, json, sys
import pdfplumber

BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "score_rank_pdf")

NUM_RE = re.compile(r"^[0-9,]+$")
MARKER_RE = re.compile(r"[及以]")  # 顶部 "708及以上" 这类最高分桶标记

def title_of(pdf):
    for p in pdf.pages:
        t = p.extract_text() or ""
        m = re.search(r"成绩统计表\(([^)]+)\)", t)
        if m:
            return m.group(1)
    return None

def identify(title):
    """返回 (subject, category)"""
    if "物理" in title:
        subject = "物理学科类"
    elif "历史" in title:
        subject = "历史学科类"
    else:
        subject = None
    if "体育" in title:
        category = "体育类"
    elif "艺术" in title:
        category = "艺术类"
    else:
        category = "普通类"
    return subject, category

def parse_pdf(path):
    rows = []
    with pdfplumber.open(path) as pdf:
        title = title_of(pdf)
        for p in pdf.pages:
            words = p.extract_words(use_text_flow=False, keep_blank_chars=False)
            if not words:
                continue
            header = [w for w in words if w["text"] == "分数"]
            if not header:
                sx = getattr(p, "_sx", None)
                cx = getattr(p, "_cx", None)
                htop = getattr(p, "_htop", None)
                if not sx or htop is None:
                    continue
            else:
                sx = sorted(w["x0"] for w in header)
                # 累计 表头锚点（可能含 '累计生' 等水印污染，但只要含 '累计' 即可）
                cx = sorted(w["x0"] for w in words if "累计" in w["text"])
                htop = min(w["top"] for w in header)
                p._sx, p._cx, p._htop = sx, cx, htop
            n = len(sx)
            # 栏边界：放在 本栏"累计" 与 下一栏"分数" 的中点，避免下一栏分数左溢
            bnd = [sx[0] - 25]
            for i in range(n - 1):
                c_i = cx[i] if i < len(cx) else sx[i] + 70
                bnd.append((c_i + sx[i + 1]) / 2)
            bnd.append((cx[-1] if cx else sx[-1] + 70) + 35)
            data = [w for w in words if w["top"] > htop + 4 and w["top"] > 0]
            col_words = [[] for _ in range(n)]
            for w in data:
                ci = None
                for i in range(n):
                    if bnd[i] <= w["x0"] < bnd[i + 1]:
                        ci = i
                        break
                if ci is None:
                    continue
                col_words[ci].append(w)
            for ci in range(n):
                cw = sorted(col_words[ci], key=lambda w: (round(w["top"]), w["x0"]))
                rows_in_col = []
                cur = []
                cur_top = None
                for w in cw:
                    if cur_top is None or abs(w["top"] - cur_top) <= 6:
                        cur.append(w)
                        cur_top = w["top"] if cur_top is None else cur_top
                    else:
                        rows_in_col.append(cur)
                        cur = [w]
                        cur_top = w["top"]
                if cur:
                    rows_in_col.append(cur)
                for r in rows_in_col:
                    # 每个词：剥离水印中文字符后取数字；"及/以/上" 视为顶部最高分桶标记
                    toks = []  # ('m', num|None) 或 ('n', num)
                    for w in sorted(r, key=lambda w: w["x0"]):
                        text = w["text"]
                        d = re.sub(r"\D", "", text)
                        d = int(d) if d else None
                        mk = bool(re.search(r"[及以]", text))
                        if d is None and not mk:
                            continue  # 纯水印中文字符，丢弃
                        toks.append(("m", d) if mk else ("n", d))
                    ms = [t for t in toks if t[0] == "m"]
                    ns = [t[1] for t in toks if t[0] == "n"]
                    if ms:
                        score = next((m[1] for m in ms if m[1] is not None), None)
                        if score is None or len(ns) < 2:
                            continue
                        count, cum = ns[0], ns[1]
                        is_top = True
                    else:
                        if len(ns) < 3:
                            continue
                        score, count, cum = ns[0], ns[1], ns[2]
                        is_top = False
                    rows.append((score, count, cum, is_top))
    return title, rows

def build_records(base_dir=BASE):
    """解析全部 12 张 PDF，返回结构化记录列表。

    累计人数(cumulative_rank) = 自最高分起 count 的累加（即">=该分人数"=省排名），
    不采用 PDF 内被水印污染的"累计"列，改由 count 重算，可消除水印造成的个别坏值。
    """
    recs = []
    for year in ["2024", "2025", "2026"]:
        d = os.path.join(base_dir, year)
        for path in sorted(glob.glob(os.path.join(d, "*.pdf"))):
            title, rows = parse_pdf(path)
            if not rows or title is None:
                continue
            subject, category = identify(title)
            sr = sorted(rows, key=lambda r: -r[0])
            run = 0
            for sc, cnt, _cum, is_top in sr:
                if sc <= 0 or cnt <= 0:
                    continue
                run += cnt
                recs.append({
                    "year": int(year), "subject": subject, "category": category,
                    "score": sc, "count": cnt, "cumulative_rank": run,
                    "is_top_bucket": is_top, "source": os.path.basename(path),
                })
    return recs

def clean_rows(rows):
    """按分数降序排序，去重，过滤非法行（累计<人数 视为页脚噪声），
    并基于 count 重算累计_rank 与官方累计做对比。"""
    # 去重（同分保留首个）
    seen = {}
    for r in rows:
        if r[0] not in seen:
            seen[r[0]] = r
    uniq = sorted(seen.values(), key=lambda r: -r[0])
    # 过滤：累计必须 >= 人数
    uniq = [r for r in uniq if r[2] >= r[1]]
    # 按分数降序后，累计应单调不减（分数越低，>=该分人数越多）
    out = []
    prev_cum = None
    for r in uniq:
        if prev_cum is not None and r[2] < prev_cum:
            continue  # 累计回落，必为噪声
        out.append(r)
        prev_cum = r[2]
    # 重算累计对比
    calc = 0
    mism = 0
    for r in out:
        calc += r[1]
        if abs(calc - r[2]) > max(2, r[2] * 0.001):
            mism += 1
    return out, mism

def main():
    recs = build_records()
    from collections import defaultdict
    stats = defaultdict(lambda: {"n": 0, "top": None, "total": None, "smax": None})
    for r in recs:
        k = (r["year"], r["subject"], r["category"])
        s = stats[k]
        s["n"] += 1
        s["total"] = r["cumulative_rank"]
        if s["top"] is None or r["score"] > s["top"]:
            s["top"] = r["score"]
        if s["smax"] is None or r["score"] < s["smax"]:
            s["smax"] = r["score"]
    print(f"TOTAL records={len(recs)}")
    for k in sorted(stats):
        s = stats[k]
        print(f"  {k[0]} {k[1]} {k[2]}: n={s['n']} score[{s['smax']}..{s['top']}] totalCum={s['total']}")

if __name__ == "__main__":
    main()
