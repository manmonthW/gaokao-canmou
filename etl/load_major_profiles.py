#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_major_profiles.py
======================
补齐 admission_scores 缺失的专业级属性：选科要求 / 学制 / 学费 / 计划数 / 硕博点 / 学科水平。

数据源（混合多源，按字段级融合）：
  A. dxsbb 招生计划页（部分校有完整11列：选科/学制/学费/计划数）
  B. youzy 分专业招生计划（计划数，按 历史类/物理类 拆分）
  C. 学校招生章程/官网（学费/学制 兜底）
  D. 教育部学科评估 / 软科（硕博点 / 学科水平）

用法：
  python3 load_major_profiles.py --school "大连理工大学"
  python3 load_major_profiles.py --all            # 全量（1594校）
  python3 load_major_profiles.py --test           # 典型学校跑通流程（5所）
  python3 load_major_profiles.py --coverage       # 打印字段覆盖率报告
"""
import argparse, re, sys, ssl, html, json, time, urllib.request
from urllib.parse import quote
import psycopg2

# ---------- 配置 ----------
DB = dict(host="localhost", port=5432, dbname="gaokao", user="gaokao", password="gaokao123")
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
ctx = ssl.create_default_context(); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE

# dxsbb 学校名 -> 页面ID（已验证，后续可自动探测补全）
DXSBB_IDS = {
    "沈阳师范大学": 101299, "东北财经大学": 101302, "大连医科大学": 101293,
    "辽宁大学": 101227, "大连理工大学": 101228, "大连医科大学中山学院": 101329,
}

# 典型学校（test 模式）
TYPICAL = ["大连理工大学", "辽宁大学", "大连医科大学", "东北财经大学", "沈阳师范大学"]


def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    return urllib.request.urlopen(req, timeout=timeout, context=ctx).read().decode("utf-8", "ignore")


def get_table_rows(html_text):
    """返回第一个 <table> 的行列表，每行是清洗后的单元格列表。"""
    i = html_text.find("<table")
    if i < 0:
        return []
    j = html_text.find("</table>", i)
    if j < 0:
        return []
    tbl = html_text[i:j + 8]
    rows = []
    for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", tbl, re.S):
        tds = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip()
               for x in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
        if tds:
            rows.append(tds)
    return rows


TUITION_RE = re.compile(r"(\d{3,5})\s*元/年|学费[:：]?\s*(\d{3,5})|(\d{3,5})\s*元")


def parse_tuition(note):
    """从专业备注中解析学费（元/年）。"""
    if not note:
        return None
    m = TUITION_RE.search(note)
    if m:
        val = m.group(1) or m.group(2) or m.group(3)
        if val:
            v = int(val)
            return v if 1000 <= v <= 100000 else None
    return None


def parse_dxsbb(school_name, year=2025):
    """解析 dxsbb 招生计划页（完整11列）。返回 major_profiles 行 dict 列表。"""
    sid = DXSBB_IDS.get(school_name)
    if not sid:
        return []
    url = f"https://www.dxsbb.com/news/{sid}.html"
    try:
        h = fetch(url)
    except Exception as e:
        print(f"  [dxsbb] {school_name} 抓取失败: {e}")
        return []
    rows = get_table_rows(h)
    out = []
    for r in rows[1:]:
        # 列: 年份 省份 层次 专业名称 招考方向 计划数 学制 专业备注 办学地点 科类 考试科目要求
        if len(r) < 11:
            continue
        major = r[3].strip()
        if not major or major in ("专业名称",):
            continue
        plan = re.sub(r"\D", "", r[5]) or None
        rec = dict(
            school_code=None,  # 稍后按校名查库补全
            major_code=None,
            major_name=major,
            year=year,
            category=r[9].strip() if len(r) > 9 else None,
            subject_req=r[10].strip() if len(r) > 10 else None,
            length=r[6].strip() or None,
            tuition=parse_tuition(r[7]),
            plan_count=int(plan) if plan else None,
            plan_count_hist=None,
            plan_count_phys=None,
            source="dxsbb",
            raw_note=r[7].strip(),
        )
        out.append(rec)
    return out


def upsert(conn, school_code, rec):
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO major_profiles
              (school_code, major_code, major_name, year, category, subject_req,
               length, tuition, plan_count, plan_count_hist, plan_count_phys, source, raw_note)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (school_code, major_code, major_name, year, category)
            DO UPDATE SET
              subject_req = COALESCE(EXCLUDED.subject_req, major_profiles.subject_req),
              length      = COALESCE(EXCLUDED.length, major_profiles.length),
              tuition     = COALESCE(EXCLUDED.tuition, major_profiles.tuition),
              plan_count  = COALESCE(EXCLUDED.plan_count, major_profiles.plan_count),
              source      = EXCLUDED.source,
              raw_note    = COALESCE(EXCLUDED.raw_note, major_profiles.raw_note),
              enriched_at = now();
        """, (
            school_code, rec.get("major_code"), rec["major_name"], rec["year"], rec.get("category"),
            rec.get("subject_req"), rec.get("length"), rec.get("tuition"),
            rec.get("plan_count"), rec.get("plan_count_hist"), rec.get("plan_count_phys"),
            rec.get("source"), rec.get("raw_note"),
        ))


def school_code_by_name(conn, name):
    with conn.cursor() as cur:
        cur.execute("SELECT code FROM schools WHERE name=%s OR name LIKE %s LIMIT 1", (name, name + "%"))
        row = cur.fetchone()
        return row[0] if row else None


def run_school(conn, name):
    print(f">> 处理: {name}")
    code = school_code_by_name(conn, name)
    if not code:
        print(f"  [warn] 库中无该校: {name}")
        return 0
    recs = parse_dxsbb(name)
    n = 0
    for r in recs:
        r["school_code"] = code
        upsert(conn, code, r)
        n += 1
    conn.commit()
    print(f"  dxsbb 写入 {n} 条（school_code={code}）")
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--school")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--coverage", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(**DB)

    if args.coverage:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM major_profiles")
            total = cur.fetchone()[0]
            for col in ["subject_req", "length", "tuition", "plan_count", "has_master", "has_doctor", "discipline_level"]:
                cur.execute(f"SELECT count(*) FROM major_profiles WHERE {col} IS NOT NULL")
                c = cur.fetchone()[0]
                print(f"  {col:16s}: {c}/{total}  ({100*c//total if total else 0}%)")
        conn.close()
        return

    targets = []
    if args.test:
        targets = TYPICAL
    elif args.all:
        with conn.cursor() as cur:
            cur.execute("SELECT DISTINCT name FROM schools ORDER BY name")
            targets = [r[0] for r in cur.fetchall()]
    elif args.school:
        targets = [args.school]

    total_written = 0
    for name in targets:
        try:
            total_written += run_school(conn, name)
        except Exception as e:
            print(f"  [error] {name}: {e}")
        time.sleep(0.3)
    print(f"\n完成。共写入 {total_written} 条。")
    conn.close()


if __name__ == "__main__":
    main()
