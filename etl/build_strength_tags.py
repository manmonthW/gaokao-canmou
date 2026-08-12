#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_strength_tags.py —— school_profiles.strength_tags 全量幂等重算（migration 0014）。

从明细表 school_disciplines + major_strengths 聚合出院校级实力标签，
全量重算写回 school_profiles.strength_tags（模式克隆 load_major_flags.py：
先算全量 → 批量 UPDATE → 未命中院校清零，保证规则迭代后旧标不残留）。

标签规则（值域只允许 strength_dictionary 中已存在的 tag）：
  - eval4_official 且 verify_status='verified'：grade A+/A/A- →
    「四轮A+」「四轮A」「四轮A-」；B 及以下不生成校级标签
    （校级只展示头部实力，B/C 档数量巨大且无区分展示价值）。
  - eval5_a 仅 verify_status='verified' 行：A+/A/A- → 「五轮A+」等；
    非官方语义由词表 source_note 自带，标签本身不加前缀。
  - dfc2022 → 「双一流学科」。
  - major_strengths 存在 swyc_national 行（该校）→ 「国一流专业」；
    swyc_provincial → 「省一流专业」。
  - 软科（ruanke）只保留专业级明细行，不生成校级「软科评级」标签：
    第三方评级覆盖 3 万+ 专业条目，几乎校校有份，挂到校上无区分度
    且有误导（官方页展示第三方结论）风险，词表保留该 tag 供未来
    专业级展示使用。
  - 「多源印证」判定见 has_multi_source_evidence()。

运行:
  python3 etl/build_strength_tags.py --dry-run   # 只统计+打印样例，不写库
  python3 etl/build_strength_tags.py             # 全量重算写库（幂等）
"""
import argparse
import sys
from collections import defaultdict

import psycopg2
import psycopg2.extras

from config import DSN

# grade → 标签后缀（四轮/五轮共用同一映射，前缀按来源区分）
GRADE_TAG = {"A+": "A+", "A": "A", "A-": "A-"}
# 学科类明细来源 → 标签前缀（B 及以下不产生校级标签，GRADE_TAG 查不到即丢弃）
DISC_SOURCE_PREFIX = {"eval4_official": "四轮", "eval5_a": "五轮"}
# 「多源印证」认可的独立学科来源集合
INDEPENDENT_DISC_SOURCES = {"eval4_official", "eval5_a", "dfc2022"}
# 标签 kind 分类：学科类 vs 专业类（多源印证的第二条判定用）
DISCIPLINE_KINDS = {"eval4", "eval5", "dfc2022"}
MAJOR_KINDS = {"swyc"}


def discipline_tags_from_rows(disc_rows):
    """学科明细行 → (该校标签集合, 命中的 kind 集合)。

    disc_rows: [(source, verify_status, grade), ...]，同一所学校的全部学科行。
    门禁统一前置：任何来源（含 dfc2022）都只认 verify_status='verified' 行
    （W4：dfc 当前加载即 verified，行为不变，但规则迭代后不产生门禁豁免）。
    学科→来源的多源印证映射由调用方另行维护（需要学科名维度）。
    """
    tags, kinds = set(), set()
    for source, verify_status, grade in disc_rows:
        if verify_status != "verified":
            continue
        if source == "dfc2022":
            tags.add("双一流学科")
            kinds.add("dfc2022")
            continue
        prefix = DISC_SOURCE_PREFIX.get(source)
        if not prefix or grade not in GRADE_TAG:
            continue  # B 及以下不生成校级标签
        tags.add(f"{prefix}{GRADE_TAG[grade]}")
        kinds.add("eval4" if source == "eval4_official" else "eval5")
    return tags, kinds


def has_multi_source_evidence(disc_source_sets, kinds):
    """判定该校是否挂「多源印证」。用平实话说，两条满足其一即可：

    1) 同一个学科被 ≥2 个互不隶属的来源同时认可（第四轮评估 / 第五轮
       A 类已核实行 / 双一流名单）。两个来源各自独立采集，都认可同一
       学科，说明该学科实力经得起交叉检验。
    2) 该校既有「学科类」认可（评估/双一流），又有「专业类」认可
       （国家级/省级一流专业），即 ≥2 类不同 kind 的标签并存——
       学科与专业是两个独立评价体系，双料同样说明实力可信。
    """
    for sources in disc_source_sets.values():
        if len(sources & INDEPENDENT_DISC_SOURCES) >= 2:
            return True
    return len(kinds & DISCIPLINE_KINDS) >= 1 and len(kinds & MAJOR_KINDS) >= 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计与打印样例，不写库")
    ap.add_argument("--samples", type=int, default=6, help="每类变更打印的样例数")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()

    # 标签值域守卫：只允许词表内 tag（前端展示/筛选的统一来源）
    cur.execute("SELECT tag FROM strength_dictionary")
    known_tags = {r[0] for r in cur.fetchall()}
    if not known_tags:
        print("[错误] strength_dictionary 为空，请先执行 migration 0014 种子数据")
        return 1
    cur.execute("SELECT tag, display_order FROM strength_dictionary")
    order = {t: o for t, o in cur.fetchall()}

    # 院校名 → code（明细行 school_code 为空时按名补解析）
    cur.execute("SELECT code, name FROM schools")
    name2code = {n: c for c, n in cur.fetchall()}

    def school_key(code, name):
        """明细行归一到 schools.code；无法解析返回 None（跳过并计数）。"""
        if code:
            return code
        return name2code.get(name)

    # ---- 聚合明细 ----
    disc_rows = defaultdict(list)   # code -> [(source, verify_status, grade), ...]
    disc_by_name = defaultdict(set)  # code -> {discipline_name}（多源印证用）
    disc_src_map = defaultdict(lambda: defaultdict(set))  # code -> 学科 -> 来源集合
    major_sources = defaultdict(set)  # code -> {swyc_national/swyc_provincial/ruanke}
    unresolved = 0

    cur.execute("""SELECT school_code, school_name, discipline_name, source,
                          verify_status, grade FROM school_disciplines""")
    for code, name, disc, source, vs, grade in cur.fetchall():
        k = school_key(code, name)
        if k is None:
            unresolved += 1
            continue
        disc_rows[k].append((source, vs, grade))
        if source in INDEPENDENT_DISC_SOURCES and vs in ("verified",):
            if source == "dfc2022" and grade == "dfc":
                continue  # 北大/清华自主公布形态无具体学科名
            disc_src_map[k][disc].add(source)

    cur.execute("SELECT school_code, school_name, source FROM major_strengths")
    for code, name, source in cur.fetchall():
        k = school_key(code, name)
        if k is None:
            unresolved += 1
            continue
        major_sources[k].add(source)

    # ---- 逐校计算目标标签 ----
    computed = {}  # code -> sorted tag list
    for code in set(disc_rows) | set(major_sources):
        tags, kinds = discipline_tags_from_rows(disc_rows.get(code, []))
        if "swyc_national" in major_sources.get(code, ()):
            tags.add("国一流专业")
            kinds.add("swyc")
        if "swyc_provincial" in major_sources.get(code, ()):
            tags.add("省一流专业")
            kinds.add("swyc")
        # ruanke 不产生校级标签（见文件头注释）
        if has_multi_source_evidence(disc_src_map.get(code, {}), kinds):
            tags.add("多源印证")
            kinds.add("meta")
        bad = tags - known_tags
        if bad:
            print(f"[错误] 生成词表外标签 {bad}（校 {code}），拒绝写库")
            return 1
        if tags:
            computed[code] = sorted(tags, key=lambda t: order[t])
    if unresolved:
        print(f"[警告] {unresolved} 条明细行 school_code 为空且校名无法解析，已跳过")

    # ---- 与现状对比 ----
    cur.execute("SELECT code, strength_tags FROM school_profiles")
    current = {c: list(t or []) for c, t in cur.fetchall()}

    added, changed, cleared, same = [], [], [], 0
    for code, cur_tags in current.items():
        new_tags = computed.get(code, [])
        if not cur_tags and new_tags:
            added.append((code, new_tags))
        elif cur_tags and not new_tags:
            cleared.append((code, cur_tags))
        elif sorted(cur_tags) != sorted(new_tags):
            changed.append((code, cur_tags, new_tags))
        else:
            same += 1

    tag_counter = defaultdict(int)
    for tags in computed.values():
        for t in tags:
            tag_counter[t] += 1

    print(f"院校总数 {len(current)} | 命中任一标签 {len(computed)} 所")
    print("标签分布:")
    for t in sorted(tag_counter, key=lambda x: order[x]):
        print(f"  [{t}] {tag_counter[t]} 所")
    print(f"变更统计: 新增 {len(added)} | 变更 {len(changed)} | "
          f"清零 {len(cleared)} | 不变 {same}")
    for title, rows in (("新增样例", [(c, t) for c, t in added]),
                        ("变更样例", [(c, t2) for c, t1, t2 in changed]),
                        ("清零样例", [(c, t) for c, t in cleared])):
        print(f"{title}:")
        for code, tags in rows[:args.samples]:
            print(f"    {code}: {tags}")

    if args.dry_run:
        print("\n[dry-run] 未写库。确认统计无误后去掉 --dry-run 重跑。")
        return 0

    updates = [(tags, code) for code, tags in computed.items()]
    psycopg2.extras.execute_batch(
        cur, "UPDATE school_profiles SET strength_tags=%s WHERE code=%s",
        updates, page_size=2000)
    # 未命中院校清零（保证幂等全量重算语义：规则迭代后旧标不残留，
    # 语义同 load_major_flags.py L109-111）
    cur.execute(
        "UPDATE school_profiles SET strength_tags='{}' "
        "WHERE strength_tags <> '{}' AND code NOT IN (SELECT unnest(%s::text[]))",
        ([code for _, code in updates] or [""] ,))
    conn.commit()
    cur.execute("SELECT count(*) FROM school_profiles WHERE strength_tags <> '{}'")
    print(f"写库完成：strength_tags 非空 {cur.fetchone()[0]} 所")
    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
