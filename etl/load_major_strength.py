#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""load_major_strength.py —— 院校学科实力 / 专业强度数据灌库（migration 0014）。

五个数据源分别写入 school_disciplines（学科粒度）与 major_strengths（专业粒度）：
  --eval4   第四轮学科评估（etl/data/eval4_official.csv，官方）
  --dfc     第二轮「双一流」建设学科（etl/data/dfc2022.csv，官方）
  --swyc    双万计划一流本科专业建设点（etl/data/swyc_batches.csv，官方）
  --ruanke  软科 2026 专业排名评级（etl/data/ruanke2026.csv，第三方·仅供参考）
  --eval5a  第五轮学科评估 A 类转录（etl/data/eval5_a_transcript.csv，非官方，
            须先过 verify_eval5.py 人工裁决门禁，默认只加载裁决为 verified 的行）

公共参数：
  --dry-run   只解析+匹配+打印统计，不写任何表
  --coverage  打印各表行数 / 按 source 分布 / school_code 解析率 / 未匹配数

设计决策（与任务约定一致，逐条说明）：
  1) 院校名解析复用 load_baoyan_rate.py 匹配器惯例：
     精确命中 schools.name → 最长前缀（校名 ≥4 字且残余 ≤3 字噪声）→ _ALIASES
     人工别名 → 未匹配清单。
  2) 未匹配行绝不静默丢弃：实际加载时逐行追加 etl/enrich_review.jsonl
     （供后续人工补解析），并在汇总中打印；dry-run 只打印不落该文件，
     避免重复试跑把清单越写越长。
  3) 未匹配行的数据本身仍以 school_code=NULL 入库（二选一的决定在此）：
     migration 0014 明确 school_code 可空 = 「允许先入库后解析」，保留事实
     比按匹配器惯例丢弃更安全——实力记录不因代码缺失而灭失，
     后续可用 enrich_review.jsonl 回填代码。
  4) upsert 一律 ON CONFLICT (唯一键) DO UPDATE SET 列 = COALESCE(EXCLUDED.x, 原值)：
     重复灌入只补空不覆盖已有值，天然幂等（模式同 load_major_profiles.py）。
  5) source_files 每个 CSV 登记一行，ON CONFLICT 走语义唯一索引
     uq_source_files_semantic（migration 0008），RETURNING id 回填到明细行
     src_file_id（模式同 load_subject_requirements.py）。
  6) major_strengths.data_year 为 NOT NULL，而 swyc 的 batch_year 约 96% 为空：
     空值记 0 哨兵（= 批次公布年未知），不虚构 2019/2020/2021；
     唯一键 (source, data_year, school_name, major_name) 中 0 不影响去重语义。

用法：
  python3 etl/load_major_strength.py --eval4 --dry-run
  python3 etl/load_major_strength.py --eval4 --dfc --swyc --ruanke   # 实际灌库
  python3 etl/load_major_strength.py --eval5a                        # 须先有裁决文件
  python3 etl/load_major_strength.py --coverage
"""
import argparse
import csv
import json
import os
import sys
from collections import Counter

import psycopg2
import psycopg2.extras

from config import DSN, BASE_DIR

DATA_DIR = os.path.join(BASE_DIR, "etl", "data")
REVIEW_JSONL = os.path.join(BASE_DIR, "etl", "enrich_review.jsonl")

# 各源固定字段与 source_files 登记口径（note 含真实来源与说明）
SOURCES = {
    "eval4": dict(
        csv="eval4_official.csv", table="school_disciplines",
        source="eval4_official", data_year=2017, official=True,
        verify_status="verified",
        file_year=2017,
        file_note=("第四轮学科评估结果（2017 年公布）：acabridge 官方授权数据整理，"
                   "与教育部学位中心公布结果一致 https://www.acabridge.edu.cn/")),
    "dfc": dict(
        csv="dfc2022.csv", table="school_disciplines",
        source="dfc2022", data_year=2022, official=True,
        verify_status="verified",
        file_year=2022,
        file_note=("第二轮「双一流」建设高校及建设学科名单（2022 年公布），"
                   "教育部 财政部 国家发展改革委 教研函〔2022〕1号 "
                   "http://www.moe.gov.cn/")),
    "swyc": dict(
        csv="swyc_batches.csv", table="major_strengths",
        file_year=2021,
        file_note=("「双万计划」国家级/省级一流本科专业建设点名单汇总（2019-2021 三批）："
                   "eol 静态 API 汇总 https://www.eol.cn/ 。官方名单为分送制、"
                   "无统一完整公开库，本表覆盖率约 97%")),
    "ruanke": dict(
        csv="ruanke2026.csv", table="major_strengths",
        source="ruanke", data_year=2026,
        file_year=2026,
        file_note=("软科 2026 中国大学专业排名评级（第三方数据·仅供参考）"
                   " https://www.shanghairanking.cn/")),
    "eval5a": dict(
        csv="eval5_a_transcript.csv", table="school_disciplines",
        source="eval5_a", data_year=2022, official=False,
        verify_status="verified",  # 实际按裁决文件 verdict 取值
        file_year=2022,
        file_note=("第五轮学科评估 A 类结果非官方汇总版转录（各校公开发布喜报整理），"
                   "官方未集中公布；入库前须经 verify_eval5.py 人工裁决门禁")),
}
ADJUDICATION_CSV = os.path.join(DATA_DIR, "eval5a_adjudication.csv")

# 人工核验的更名/噪声别名（沿用 load_baoyan_rate.py 惯例，按源补充）。
# 只收录「库内新名唯一确定」的更名；「中国地质大学/中国石油大学/华北电力大学」
# 等裸名对应两个校区实体，无法安全推断归属——eval5a 仅按学科归属裁决映射
# 2 条（见 _EVAL5A_DISC_ALIASES），其余留 enrich_review.jsonl 人工裁决。
_ALIASES = {
    "华北电力大学（保定)": "华北电力大学(保定)",  # 全/半角括号混用
    "郑州轻工业学院": "郑州轻工业大学",          # 2018 更名，库内唯一
    "上海电力学院": "上海电力大学",              # 2018 更名，库内唯一
    "上海体育学院": "上海体育大学",              # 2023 更名，库内唯一
}

# eval5a 专用「按学科归属」别名（S5 用户签字裁决）：裸名对应两个校区实体时，
# 仅对有客观归属依据的 (院校,学科) 组合做映射，依据逐条记录在裁决文件
# etl/data/eval5a_adjudication.csv 的 note 列；无依据的裸名组合保持
# disputed 不入库，绝不猜测。键 = (转录院校名, 学科名) → 库内校名。
_EVAL5A_DISC_ALIASES = {
    # 地质学为中国地质大学(武汉)「双一流」建设学科与公认王牌学科
    ("中国地质大学", "地质学"): "中国地质大学(武汉)",
    # 电气工程为华北电力大学标志性学科，办学主体与学科资源在北京校区
    ("华北电力大学", "电气工程"): "华北电力大学(北京)",
}


def _clean(v):
    """空串归一为 None（与 load_subject_requirements._clean 同语义）。"""
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def _int(v):
    """容错整数解析：非数字/空 → None。"""
    s = _clean(v)
    if s is None:
        return None
    try:
        return int(float(s))
    except ValueError:
        return None


def read_csv(name):
    path = os.path.join(DATA_DIR, name)
    if not os.path.exists(path):
        print(f"[错误] 输入文件不存在: {path}")
        sys.exit(1)
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class NameMatcher:
    """院校名 → schools.code 匹配器（精确 → 最长前缀 → 别名 → 未匹配清单）。

    复用 load_baoyan_rate.py L30-97 的匹配惯例：
      - 精确命中 schools.name；
      - 最长前缀：库内校名 ≥4 字、为输入名前缀、尾部噪声 ≤3 字，
        按名称长度降序优先命中最完整校名；
      - _ALIASES 人工别名先做归一；
      - 仍未命中进入 unmatched 清单，绝不静默丢弃。
    """

    def __init__(self, conn):
        cur = conn.cursor()
        cur.execute("SELECT code, name FROM schools")
        self.name2code = {n: c for c, n in cur.fetchall()}
        self.all_names = sorted(self.name2code, key=len, reverse=True)
        self.cache = {}

    def resolve(self, raw_name):
        """返回 (school_code 或 None, 展示名)；未匹配返回 (None, 原名)。"""
        if raw_name in self.cache:
            return self.cache[raw_name]
        clean = _ALIASES.get(raw_name) or (raw_name or "").replace("　", "").strip()
        # 素材多用全角括号、库内统一半角：先归一再精确匹配
        clean = clean.replace("（", "(").replace("）", ")")
        if clean in self.name2code:
            r = (self.name2code[clean], clean)
        else:
            hit = next((n for n in self.all_names
                        if len(n) >= 4 and clean.startswith(n)
                        and len(clean) - len(n) <= 3), None)
            r = (self.name2code[hit], f"{raw_name}→{hit}") if hit else (None, raw_name)
        self.cache[raw_name] = r
        return r


def register_source_file(cur, key):
    """登记/复用 source_files 一行并返回 id（模式同 load_subject_requirements）。

    ON CONFLICT 走语义唯一索引 uq_source_files_semantic（0008）：
    重复运行只刷新 note/loaded_at，不新增重复行。
    """
    cfg = SOURCES[key]
    cur.execute(
        """INSERT INTO source_files (filename, fmt, year, status, note, loaded_at)
           VALUES (%s, 'csv', %s, 'loaded', %s, now())
           ON CONFLICT (filename, COALESCE(year, -1), COALESCE(category, ''),
                        COALESCE(batch, ''), COALESCE(subject, ''),
                        COALESCE(is_collection, FALSE))
           DO UPDATE SET note = EXCLUDED.note,
                         status = EXCLUDED.status,
                         loaded_at = now()
           RETURNING id""",
        (cfg["csv"], cfg["file_year"], cfg["file_note"]))
    return cur.fetchone()[0]


def log_unmatched(source_key, rows):
    """未匹配行追加 enrich_review.jsonl，保留事实供人工补解析（不静默丢弃）。

    沿用既有 {code, name, reason} 行格式（与 verify_eval5.py 写入的行一致），
    reason 标注来源：strength_<source>_school_unmatched；追加前按
    (name, reason) 对已有行去重（同 verify_eval5.py 逻辑），重跑不累积。
    """
    reason = f"strength_{source_key}_school_unmatched"
    existing = set()
    if os.path.exists(REVIEW_JSONL):
        with open(REVIEW_JSONL, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    o = json.loads(line)
                    existing.add((o.get("name"), o.get("reason")))
                except json.JSONDecodeError:
                    pass
    new_rows, seen = [], set()
    for r in rows:
        name = r["school_name"]
        if (name, reason) in existing or (name, reason) in seen:
            continue
        seen.add((name, reason))
        new_rows.append({"code": "", "name": name, "reason": reason})
    if new_rows:
        with open(REVIEW_JSONL, "a", encoding="utf-8") as f:
            for o in new_rows:
                f.write(json.dumps(o, ensure_ascii=False) + "\n")


def report(source_key, rows, matched_n, unmatched, dry_run):
    total = len(rows)
    rate = 100.0 * matched_n / total if total else 0.0
    mode = "[dry-run] " if dry_run else ""
    print(f"{mode}[{source_key}] 解析 {total} 行 | 院校匹配 {matched_n} 行 "
          f"({rate:.1f}%) | 未匹配 {len(unmatched)} 行"
          f"{'（以 school_code=NULL 入库，清单见 enrich_review.jsonl）' if unmatched and not dry_run else ''}")
    for name, n in Counter(u["school_name"] for u in unmatched).most_common(30):
        print(f"    未匹配: {name} ×{n}")
    if dry_run and len(unmatched) > 30:
        print(f"    ……另有 {len(unmatched) - 30} 行未逐条打印")


# ---------- 各源解析（返回目标表行元组列表 + 统计） ----------

def parse_disciplines(key, matcher, dry_run):
    """eval4 / dfc 解析为 school_disciplines 行。"""
    cfg = SOURCES[key]
    rows = read_csv(cfg["csv"])
    out, matched_n, unmatched = [], 0, []
    for raw in rows:
        school = _clean(raw.get("school_name"))
        if not school:
            continue
        code, _disp = matcher.resolve(school)
        if code:
            matched_n += 1
        else:
            unmatched.append(
                {"school_name": school, **{k: _clean(v) for k, v in raw.items()}})
        if key == "dfc":
            disc = _clean(raw.get("discipline_name"))
            note = _clean(raw.get("note"))
            if not disc:
                # 北大/清华「自主确定建设学科并自行公布」：discipline_name NOT NULL，
                # 以 note 文本作为学科占位、grade 记 'dfc' 标记该特殊形态（任务约定）。
                disc = note or "自主确定建设学科并自行公布"
                grade = "dfc"
            else:
                grade = None  # 双一流名单无评级（0014 表注释口径）
            review_note = note
        else:
            disc = _clean(raw.get("discipline_name"))
            if not disc:
                continue
            grade = _clean(raw.get("grade"))
            review_note = None
        out.append((code, school, disc, cfg["source"], cfg["data_year"], grade,
                    cfg["official"], cfg["verify_status"], review_note,
                    _clean(raw.get("image_ref")) if key == "eval5a" else None))
    return out, matched_n, unmatched


def upsert_disciplines(cur, rows, src_id):
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO school_disciplines
             (school_code, school_name, discipline_name, source, data_year, grade,
              official, verify_status, review_note, image_ref, src_file_id)
           VALUES %s
           ON CONFLICT (source, data_year, school_name, discipline_name)
           DO UPDATE SET
             school_code   = COALESCE(EXCLUDED.school_code, school_disciplines.school_code),
             grade         = COALESCE(EXCLUDED.grade, school_disciplines.grade),
             review_note   = COALESCE(EXCLUDED.review_note, school_disciplines.review_note),
             image_ref     = COALESCE(EXCLUDED.image_ref, school_disciplines.image_ref),
             src_file_id   = COALESCE(EXCLUDED.src_file_id, school_disciplines.src_file_id)""",
        [r + (src_id,) for r in rows], page_size=2000)


def run_discipline_source(key, conn, matcher, dry_run):
    rows, matched_n, unmatched = parse_disciplines(key, matcher, dry_run)
    report(key, rows, matched_n, unmatched, dry_run)
    if dry_run:
        return
    cur = conn.cursor()
    src_id = register_source_file(cur, key)
    upsert_disciplines(cur, rows, src_id)
    conn.commit()
    cur.execute("SELECT count(*) FROM school_disciplines WHERE source=%s",
                (SOURCES[key]["source"],))
    print(f"  [写入] school_disciplines[{SOURCES[key]['source']}] 累计 {cur.fetchone()[0]} 行")
    if unmatched:
        log_unmatched(key, unmatched)


def parse_eval5a(matcher, dry_run):
    """eval5a：默认只加载裁决文件标记 verified 的行（门禁前置）。"""
    if not os.path.exists(ADJUDICATION_CSV):
        print("[错误] 裁决文件不存在: %s" % ADJUDICATION_CSV)
        print("       请先运行 verify_eval5.py 完成人工裁决门禁，再加载 --eval5a。")
        sys.exit(1)
    verdicts = {}
    with open(ADJUDICATION_CSV, encoding="utf-8-sig", newline="") as f:
        for r in csv.DictReader(f):
            k = (_clean(r.get("school_name")), _clean(r.get("discipline_name")))
            verdicts[k] = (_clean(r.get("verdict")), _clean(r.get("note")))
    cfg = SOURCES["eval5a"]
    rows = read_csv(cfg["csv"])
    out, matched_n, unmatched = [], 0, []
    skipped, disputed, dedup = 0, 0, 0
    seen = set()  # S3 裁决：同校同学科源图重复只保留 1 行
    for raw in rows:
        school = _clean(raw.get("school_name"))
        disc = _clean(raw.get("discipline_name"))
        if not school or not disc:
            continue
        verdict, adj_note = verdicts.get((school, disc), (None, None))
        if verdict != "verified":
            disputed += verdict == "disputed"
            skipped += 1
            continue  # 门禁：未裁决/裁决非 verified 一律不入库
        if (school, disc) in seen:
            dedup += 1
            continue  # 同批重复键会触发 ON CONFLICT 二次更新错误，按裁决去重
        seen.add((school, disc))
        # S5 裁决映射仅用于解析 school_code；入库 school_name 保留转录原名
        match_name = _EVAL5A_DISC_ALIASES.get((school, disc), school)
        code, _disp = matcher.resolve(match_name)
        if code:
            matched_n += 1
        else:
            unmatched.append({"school_name": school,
                              **{k: _clean(v) for k, v in raw.items()}})
        out.append((code, school, disc, cfg["source"], cfg["data_year"],
                    _clean(raw.get("grade")), cfg["official"], "verified",
                    adj_note, _clean(raw.get("image_ref"))))
    print(f"  [门禁] 裁决 verified {len(out)} 行（批内去重 {dedup} 行）；"
          f"跳过 {skipped} 行（其中 disputed {disputed}）")
    return out, matched_n, unmatched


def parse_swyc(matcher, dry_run):
    cfg = SOURCES["swyc"]
    rows = read_csv(cfg["csv"])
    out, matched_n, unmatched = [], 0, []
    unknown_tier = 0
    for raw in rows:
        school = _clean(raw.get("school_name"))
        major = _clean(raw.get("major_name"))
        if not school or not major:
            continue
        # tier 显式匹配（W5）：只认 national/provincial 两个已知值；
        # 未知值（含空）告警跳过并计数，绝不默认归入省级。
        tier = _clean(raw.get("tier"))
        if tier == "national":
            source = "swyc_national"
        elif tier == "provincial":
            source = "swyc_provincial"
        else:
            unknown_tier += 1
            continue
        batch_year = _int(raw.get("batch_year"))
        # data_year NOT NULL：batch_year 空记 0 哨兵（批次公布年未知），不虚构年份
        data_year = batch_year if batch_year else 0
        code, _disp = matcher.resolve(school)
        if code:
            matched_n += 1
        else:
            unmatched.append({"school_name": school,
                              **{k: _clean(v) for k, v in raw.items()}})
        out.append((code, school, major, None, source, data_year,
                    _int(raw.get("batch")), None, None, None))
    if unknown_tier:
        print(f"    [警告] swyc 未知 tier 值 {unknown_tier} 行，已跳过不入库"
              "（仅认 national/provincial）")
    return out, matched_n, unmatched


def parse_ruanke(matcher, dry_run):
    cfg = SOURCES["ruanke"]
    rows = read_csv(cfg["csv"])
    out, matched_n, unmatched = [], 0, []
    for raw in rows:
        school = _clean(raw.get("school_name"))
        major = _clean(raw.get("major_name"))
        if not school or not major:
            continue
        code, _disp = matcher.resolve(school)
        if code:
            matched_n += 1
        else:
            unmatched.append({"school_name": school,
                              **{k: _clean(v) for k, v in raw.items()}})
        out.append((code, school, major, _clean(raw.get("major_code")),
                    cfg["source"], _int(raw.get("data_year")) or cfg["data_year"],
                    None, _int(raw.get("rank")), _clean(raw.get("tier")), None))
    return out, matched_n, unmatched


def upsert_strengths(cur, rows, src_id):
    psycopg2.extras.execute_values(
        cur,
        """INSERT INTO major_strengths
             (school_code, school_name, major_name, major_code, source, data_year,
              batch, rank, tier, note, src_file_id)
           VALUES %s
           ON CONFLICT (source, data_year, school_name, major_name)
           DO UPDATE SET
             school_code = COALESCE(EXCLUDED.school_code, major_strengths.school_code),
             major_code  = COALESCE(EXCLUDED.major_code, major_strengths.major_code),
             batch       = COALESCE(EXCLUDED.batch, major_strengths.batch),
             rank        = COALESCE(EXCLUDED.rank, major_strengths.rank),
             tier        = COALESCE(EXCLUDED.tier, major_strengths.tier),
             note        = COALESCE(EXCLUDED.note, major_strengths.note),
             src_file_id = COALESCE(EXCLUDED.src_file_id, major_strengths.src_file_id)""",
        [r + (src_id,) for r in rows], page_size=2000)


def run_strength_source(key, conn, matcher, dry_run):
    parser = parse_swyc if key == "swyc" else parse_ruanke
    rows, matched_n, unmatched = parser(matcher, dry_run)
    report(key, rows, matched_n, unmatched, dry_run)
    if key == "swyc":
        by_src = Counter(r[4] for r in rows)
        for s in sorted(by_src):
            print(f"    {s}: {by_src[s]} 行")
    if dry_run:
        return
    cur = conn.cursor()
    src_id = register_source_file(cur, key)
    upsert_strengths(cur, rows, src_id)
    conn.commit()
    srcs = ("swyc_national", "swyc_provincial") if key == "swyc" else ("ruanke",)
    for s in srcs:
        cur.execute("SELECT count(*) FROM major_strengths WHERE source=%s", (s,))
        print(f"  [写入] major_strengths[{s}] 累计 {cur.fetchone()[0]} 行")
    if unmatched:
        log_unmatched(key, unmatched)


def coverage(conn):
    """--coverage：行数 / source 分布 / school_code 解析率 / 未匹配（NULL 代码）数。"""
    cur = conn.cursor()
    for table in ("school_disciplines", "major_strengths"):
        cur.execute(f"SELECT count(*) FROM {table}")
        total = cur.fetchone()[0]
        print(f"\n== {table}: {total} 行 ==")
        cur.execute(f"SELECT source, count(*) FROM {table} GROUP BY source ORDER BY 1")
        for s, n in cur.fetchall():
            print(f"  source={s}: {n}")
        cur.execute(f"SELECT count(*) FROM {table} WHERE school_code IS NOT NULL")
        resolved = cur.fetchone()[0]
        cur.execute(f"SELECT count(*) FROM {table} WHERE school_code IS NULL")
        null_n = cur.fetchone()[0]
        rate = 100.0 * resolved / total if total else 0.0
        print(f"  school_code 解析率: {resolved}/{total} ({rate:.1f}%)，"
              f"未匹配(NULL) {null_n} 行")
    cur.execute("SELECT count(*) FROM strength_dictionary")
    print(f"\nstrength_dictionary: {cur.fetchone()[0]} 个标签")
    cur.execute("SELECT count(*) FROM school_profiles WHERE strength_tags <> '{}'")
    print(f"school_profiles.strength_tags 非空: {cur.fetchone()[0]} 所")


def main():
    ap = argparse.ArgumentParser()
    for k in SOURCES:
        ap.add_argument("--" + k, action="store_true", help=f"加载 {SOURCES[k]['csv']}")
    ap.add_argument("--dry-run", action="store_true", help="只解析打印不写库")
    ap.add_argument("--coverage", action="store_true", help="打印覆盖率报告")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    try:
        if args.coverage:
            coverage(conn)
            return 0
        selected = [k for k in SOURCES if getattr(args, k)]
        if not selected:
            ap.print_help()
            return 1
        matcher = NameMatcher(conn)
        for key in selected:
            print(f"\n>> 加载 {SOURCES[key]['csv']}")
            if SOURCES[key]["table"] == "school_disciplines" and key != "eval5a":
                run_discipline_source(key, conn, matcher, args.dry_run)
            elif key == "eval5a":
                rows, matched_n, unmatched = parse_eval5a(matcher, args.dry_run)
                report(key, rows, matched_n, unmatched, args.dry_run)
                if args.dry_run:
                    continue
                cur = conn.cursor()
                src_id = register_source_file(cur, key)
                upsert_disciplines(cur, rows, src_id)
                conn.commit()
                cur.execute("SELECT count(*) FROM school_disciplines WHERE source='eval5_a'")
                print(f"  [写入] school_disciplines[eval5_a] 累计 {cur.fetchone()[0]} 行")
                if unmatched:
                    log_unmatched(key, unmatched)
            else:
                run_strength_source(key, conn, matcher, args.dry_run)
        if args.dry_run:
            print("\n[dry-run] 未写任何表。确认统计无误后去掉 --dry-run 重跑。")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
