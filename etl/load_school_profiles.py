#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
load_school_profiles.py —— 院校画像自动化装载(核心维度)
数据源: 教育部《2025全国高等学校名单》Excel (moe.gov.cn, 直连可达)
  - 所在城市(所在地, 城市级) / 省份(derive) / 主管部门 / 办学层次 / 性质(备注)
  - 类型(综合/理工/师范…) 由校名启发式推导
  - 与 schools.code 通过 "标识码末4位 == code" 精确关联
仅装载出现在本校招生库(schools)中的院校。

名单回填(backfill_missing): 历年院校编号逐年轮换，新入库的校码往往不在
当年名单的标识码末4位里。对 admission_scores 已引用但 school_profiles
缺失的校码，按三级策略幂等补齐：
  ① 同名画像复制（跨年轮换码，如军校 J011→J012；含去括号后缀的校区变体）
  ② 名单 xls 按校名匹配（优先本地更新的名单文件，覆盖改名/新增院校）
  ③ 骨架行（仅 code/name + 层次启发式 + note 标记，军校等不在名单者）
"""
import os, re, requests
import psycopg2, xlrd
from config import DSN

DATA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
os.makedirs(DATA, exist_ok=True)
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124.0 Safari/537.36"
MOE_XLS = "https://www.moe.gov.cn/jyb_xxgk/s5743/s5744/A03/202506/W020250729615142156867.xls"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SUFFIXES = ["市","地区","自治州","盟","区","县","自治旗","特别行政区"]
# 本地更新的教育部名单（比在线 2025 版新则优先，用于名单按校名匹配回填）
LOCAL_ROSTER = os.path.join(
    ROOT, "2026allmaterial", "全国普通高等学校名单（截止2026年6月17日）.xls")

def norm(c: str) -> str:
    c = (c or "").strip()
    for s in SUFFIXES:
        if len(c) > len(s) and c.endswith(s):
            c = c[:-len(s)]
    return c

def derive_type(name: str) -> str:
    n = name or ""
    rules = [
        ("师范", "师范"), ("医药","医药"), ("医科","医药"), ("医学","医药"),
        ("财经","财经"), ("经贸","财经"), ("金融","财经"),
        ("农林","农林"), ("农业","农林"), ("林业","农林"),
        ("政法","政法"), ("公安","政法"), ("警务","政法"),
        ("外国语","语言"), ("外语","语言"), ("语言","语言"),
        ("民族","民族"),
        ("艺术","艺术"), ("美术","艺术"), ("音乐","艺术"), ("戏剧","艺术"), ("传媒","艺术"), ("电影","艺术"), ("戏曲","艺术"),
        ("体育","体育"),
        ("军事","军事"), ("国防","军事"), ("武警","军事"),
        ("职业技术","职业技术"), ("职业","职业技术"), ("技师","职业技术"),
        ("理工","理工"), ("工业","理工"), ("科技","理工"), ("工程","理工"), ("交通","理工"),
        ("建筑","理工"), ("邮电","理工"), ("航空","理工"), ("航天","理工"), ("电子","理工"),
        ("信息","理工"), ("化工","理工"), ("矿业","理工"), ("石油","理工"), ("电力","理工"),
        ("水利","理工"), ("海洋","理工"), ("海事","理工"), ("测绘","理工"), ("地质","理工"),
        ("机电","理工"), ("汽车","理工"), ("铁道","理工"), ("冶金","理工"),
    ]
    for kw, t in rules:
        if kw in n:
            return t
    return "综合"

def derive_nature(remark: str) -> str:
    r = remark or ""
    if "民办" in r: return "民办"
    if "独立学院" in r: return "独立学院"
    if "中外合作" in r or "内地与港澳" in r or "境外" in r: return "中外合作办学"
    return "公办"

def download_xls():
    p = os.path.join(DATA, "moe_univ_2025.xls")
    if not os.path.exists(p):
        r = requests.get(MOE_XLS, headers={"User-Agent": UA}, timeout=60)
        r.raise_for_status()
        open(p, "wb").write(r.content)
    return p

def parse_roster(p):
    """解析教育部名单 xls → (rows, by_name)。
    rows: [(name, code4, affiliation, city(已norm), level, remark)]；
    by_name: 校名 → 首条 row（名单内校名唯一）。"""
    wb = xlrd.open_workbook(p)
    ws = wb.sheet_by_index(0)
    rows, by_name = [], {}
    for r in range(ws.nrows):
        seq = ws.cell_value(r, 0)
        name = str(ws.cell_value(r, 1)).strip()
        if not (isinstance(seq, (int, float)) and name):
            continue  # 跳过表头/省份分组行
        code10 = str(int(ws.cell_value(r, 2)))
        rec = (name, code10[-4:],
               str(ws.cell_value(r, 3)).strip(),
               norm(str(ws.cell_value(r, 4))),
               "本科" if "本科" in str(ws.cell_value(r, 5)) else "高职专科",
               str(ws.cell_value(r, 6)).strip())
        rows.append(rec)
        by_name.setdefault(name, rec)
    return rows, by_name

def upsert_profile(cur, code, name, city, province, affiliation, level, nature, stype, note):
    cur.execute("""INSERT INTO school_profiles
        (code,name,city,province,affiliation,level,nature,type,note)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (code) DO UPDATE SET
          name=EXCLUDED.name, city=EXCLUDED.city, province=EXCLUDED.province,
          affiliation=EXCLUDED.affiliation, level=EXCLUDED.level,
          nature=EXCLUDED.nature, type=EXCLUDED.type,
          note=CASE WHEN school_profiles.note IS NULL THEN EXCLUDED.note ELSE school_profiles.note END""",
        (code, name, city, province, affiliation, level, nature, stype, note))

def backfill_missing(cur, by_name):
    """回填 admission_scores 已引用但 school_profiles 缺失的校码（见模块 docstring）。
    幂等：重跑时 missing 集为空即无操作。"""
    cur.execute("""
        SELECT DISTINCT a.school_code, COALESCE(s.name, a.school_name)
        FROM admission_scores a
        LEFT JOIN schools s ON s.code = a.school_code
        WHERE a.school_code IS NOT NULL
          AND NOT EXISTS (SELECT 1 FROM school_profiles p WHERE p.code = a.school_code)
        ORDER BY a.school_code""")
    missing = cur.fetchall()
    n_copy = n_roster = n_skel = 0
    for code, name in missing:
        name = (name or "").strip()
        # ① 同名画像复制（跨年轮换码：军校/校区等同名不同码，画像一致）
        cur.execute("""SELECT name, city, province, affiliation, level, nature, type
                       FROM school_profiles WHERE name = %s ORDER BY code LIMIT 1""", (name,))
        row = cur.fetchone()
        copy_note = "同名画像复制(跨年轮换码)"
        if row is None:
            # 校区/招生变体：去掉括号后缀后匹配母体校（如 北京邮电大学(宏福校区)）
            base = re.sub(r"[（(][^（()）]*[）)]$", "", name).strip()
            if base != name:
                cur.execute("""SELECT name, city, province, affiliation, level, nature, type
                               FROM school_profiles WHERE name = %s ORDER BY code LIMIT 1""", (base,))
                row = cur.fetchone()
                copy_note = "同名画像复制(校区变体)"
        if row:
            # 保留本行校名（校区变体不丢后缀）；源行空字段用启发式兼底，
            # 避免把早年少字段的骨架源行 NULL 传染过来。
            upsert_profile(cur, code, name,
                           row[1], row[2], row[3],
                           row[4] or "本科",
                           row[5] or "公办",
                           row[6] or derive_type(name),
                           copy_note)
            n_copy += 1
            continue
        # ② 名单按校名匹配（改名/新增院校，用名单字段重建画像）
        rec = by_name.get(name)
        if rec:
            _rname, _code4, aff, city, level, remark = rec
            cur.execute("INSERT INTO cities (city) VALUES (%s) ON CONFLICT (city) DO NOTHING", (city,))
            cur.execute("SELECT province FROM cities WHERE city=%s", (city,))
            prow = cur.fetchone()
            province = prow[0] if prow else None
            upsert_profile(cur, code, name, city, province, aff, level,
                           derive_nature(remark), derive_type(name),
                           (remark if remark and remark not in ("公办",) else None))
            n_roster += 1
            continue
        # ③ 骨架行（军校等不在普通高校名单）：层次启发式 + note 标记
        if "职业技术大学" in name:
            level = "本科"
        elif any(k in name for k in ("职业", "专科", "高专")):
            level = "高职专科"
        else:
            level = "本科"
        upsert_profile(cur, code, name, None, None, None, level,
                       "公办", derive_type(name), "骨架画像(名单外,自动回填)")
        n_skel += 1
    print(f"名单回填: 缺口 {len(missing)} 所 → 同名复制 {n_copy} / "
          f"名单匹配 {n_roster} / 骨架 {n_skel}")
    return len(missing)

def main():
    p = download_xls()
    roster_rows, by_name = parse_roster(p)
    if os.path.exists(LOCAL_ROSTER):
        local_rows, local_by_name = parse_roster(LOCAL_ROSTER)
        print(f"使用本地更新名单 {os.path.basename(LOCAL_ROSTER)} ({len(local_rows)} 所)")
        roster_rows, by_name = local_rows, local_by_name
    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    parsed = 0; matched = 0; inserted = 0
    for name, code4, affiliation, city, level, remark in roster_rows:
        parsed += 1
        cur.execute("SELECT 1 FROM schools WHERE code=%s", (code4,))
        if not cur.fetchone():
            continue
        matched += 1
        nature = derive_nature(remark)
        stype = derive_type(name)

        # 确保 cities 有该城市(基础行, province 后续由 load_cities 补齐)
        cur.execute("INSERT INTO cities (city) VALUES (%s) ON CONFLICT (city) DO NOTHING", (city,))
        # 取 province
        cur.execute("SELECT province FROM cities WHERE city=%s", (city,))
        row = cur.fetchone()
        province = row[0] if row else None

        upsert_profile(cur, code4, name, city, province, affiliation, level, nature, stype,
                       (remark if remark and remark not in ("公办",) else None))
        inserted += 1

    # 回填轮换码/名单外缺口（幂等）
    backfill_missing(cur, by_name)

    conn.commit()
    cur.execute("SELECT count(*) FROM school_profiles")
    tot = cur.fetchone()[0]
    cur.execute("""SELECT count(DISTINCT a.school_code) FROM admission_scores a
                   WHERE a.school_code IS NOT NULL
                     AND NOT EXISTS (SELECT 1 FROM school_profiles p WHERE p.code = a.school_code)""")
    gap = cur.fetchone()[0]
    print(f"名单解析 {parsed} 行, 命中本校库 {matched} 所, 写入/更新 {inserted} 条; "
          f"school_profiles 现有 {tot} 条, 残余缺口 {gap}")
    cur.close(); conn.close()

if __name__ == "__main__":
    main()
