#!/usr/bin/env python3
"""diff_eval5_tracks.py — 第五轮学科评估 A 类汇总「双轨转录」比对。

第一轨：major/第五轮学科评估/第五轮学科评估A类汇总_提取稿.md（既有的 md 提取稿）
第二轨：etl/data/eval5_a_transcript.csv（本次逐图独立转录）

按 (学科, 档位) 分组比对院校集合，输出 etl/data/eval5a_track_diff.md：
  ① 两轨完全一致的 (学科,档位) 组数；
  ② 仅第一轨有的 (学科,档位,院校)；
  ③ 仅第二轨有的 (学科,档位,院校)；
  ④ 档位冲突（同学科同院校、两轨档位不同）。
另附统计口径、存疑清单与颜色观察（颜色仅作未核验元数据，绝不进入 CSV）。
"""
import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MD_PATH = ROOT / "major" / "第五轮学科评估" / "第五轮学科评估A类汇总_提取稿.md"
CSV_PATH = ROOT / "etl" / "data" / "eval5_a_transcript.csv"
OUT_PATH = ROOT / "etl" / "data" / "eval5a_track_diff.md"

GRADE_RE = re.compile(r"^-\s*(A\+|A-|A|B\+|B-|B|C\+)：\s*(.+)$")
DISC_RE = re.compile(r"^###\s+(.+?)\s*$")
ANNOT_RE = re.compile(r"（[^（）]*）$")  # 行尾括注，如 （续 (3)）/（原图…）


def normalize_grade(g: str) -> str:
    """全角减号/连字符统一为半角 A- 形式。"""
    return g.replace("\u2212", "-").replace("\uff0d", "-").strip()


def parse_md(path: Path):
    """返回 {(discipline, grade): set(school)} 与原始条目数。"""
    groups = defaultdict(set)
    entries = 0
    disc = None
    in_doubt = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("## 存疑待校验"):
            in_doubt = True
            disc = None
            continue
        if in_doubt:
            continue
        m = DISC_RE.match(line)
        if m:
            disc = m.group(1)
            continue
        m = GRADE_RE.match(line)
        if m and disc:
            grade = normalize_grade(m.group(1))
            for tok in m.group(2).split("、"):
                school = ANNOT_RE.sub("", tok).strip()
                if school:
                    groups[(disc, grade)].add(school)
                    entries += 1
    return groups, entries


def parse_csv(path: Path):
    """返回 {(discipline, grade): set(school)}、原始行数、每档计数。"""
    groups = defaultdict(set)
    rows = 0
    grade_count = defaultdict(int)
    with path.open(encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            disc = r["discipline_name"].strip()
            grade = normalize_grade(r["grade"])
            school = r["school_name"].strip()
            groups[(disc, grade)].add(school)
            rows += 1
            grade_count[grade] += 1
    return groups, rows, grade_count


def main():
    md_groups, md_entries = parse_md(MD_PATH)
    csv_groups, csv_rows, csv_grade_count = parse_csv(CSV_PATH)

    all_keys = sorted(
        set(md_groups) | set(csv_groups),
        key=lambda k: (k[0], k[1]),
    )
    identical = []
    only_md = []   # (disc, grade, sorted schools)
    only_csv = []
    for key in all_keys:
        s1 = md_groups.get(key, set())
        s2 = csv_groups.get(key, set())
        if s1 == s2:
            identical.append(key)
        else:
            if s1 - s2:
                only_md.append((key[0], key[1], sorted(s1 - s2)))
            if s2 - s1:
                only_csv.append((key[0], key[1], sorted(s2 - s1)))

    # ④ 档位冲突：同 (学科, 院校) 在两轨的档位集合不同
    md_gs = defaultdict(set)   # (disc, school) -> {grade}
    csv_gs = defaultdict(set)
    for (d, g), schools in md_groups.items():
        for s in schools:
            md_gs[(d, s)].add(g)
    for (d, g), schools in csv_groups.items():
        for s in schools:
            csv_gs[(d, s)].add(g)
    conflicts = []
    for key in sorted(set(md_gs) | set(csv_gs)):
        g1, g2 = md_gs.get(key, set()), csv_gs.get(key, set())
        if g1 != g2:
            conflicts.append((key[0], key[1], sorted(g1), sorted(g2)))

    # 统计口径（集合口径，重复已折叠；CSV 行数另报原始行数）
    md_discs = {d for d, _ in md_groups}
    csv_discs = {d for d, _ in csv_groups}
    md_schools = {s for ss in md_groups.values() for s in ss}
    csv_schools = {s for ss in csv_groups.values() for s in ss}

    md_grade_sets = defaultdict(set)
    for (d, g), ss in md_groups.items():
        md_grade_sets[g] |= ss
    # 注意：同一院校可出现在多学科，档位计数按条目（(学科,院校)对）统计更稳妥
    md_grade_entries = defaultdict(int)
    for (d, g), ss in md_groups.items():
        md_grade_entries[g] += len(ss)

    lines = []
    ap = lines.append
    ap("# 第五轮学科评估 A 类汇总 — 双轨转录比对报告")
    ap("")
    ap(f"- 第一轨：`major/第五轮学科评估/第五轮学科评估A类汇总_提取稿.md`")
    ap(f"- 第二轨：`etl/data/eval5_a_transcript.csv`（18 图逐图独立转录）")
    ap("")
    ap("## 统计口径")
    ap("")
    ap("| 指标 | 第一轨(md) | 第二轨(csv) |")
    ap("| --- | --- | --- |")
    ap(f"| 条目数（学科×院校） | 原始 {md_entries}，重复折叠后 {len(md_gs)} | 原始 {csv_rows}，重复折叠后 {len(csv_gs)} |")
    ap(f"| 覆盖学科数 | {len(md_discs)} | {len(csv_discs)} |")
    ap(f"| 覆盖院校数（去重） | {len(md_schools)} | {len(csv_schools)} |")
    ap("")
    ap("第二轨每档条目数（原始行，含如实转录的 B+/B/B-/C+ 行）：")
    ap("")
    ap("| 档位 | A+ | A | A- | B+ | B | B- | C+ |")
    ap("| --- | --- | --- | --- | --- | --- | --- | --- |")
    ap("| 行数 | " + " | ".join(
        str(csv_grade_count.get(g, 0)) for g in ["A+", "A", "A-", "B+", "B", "B-", "C+"]
    ) + " |")
    ap("")
    ap(f"第一轨每档条目数：A+ {md_grade_entries['A+']}、A {md_grade_entries['A']}、"
       f"A- {md_grade_entries['A-']}、B+ {md_grade_entries['B+']}、B {md_grade_entries['B']}、"
       f"B- {md_grade_entries['B-']}、C+ {md_grade_entries['C+']}。")
    ap("")
    ap("## ① 两轨完全一致")
    ap("")
    ap(f"(学科, 档位) 分组共 {len(all_keys)} 组，其中两轨院校集合完全一致 **{len(identical)}** 组，"
       f"不一致 {len(all_keys) - len(identical)} 组。一致率 {len(identical)/len(all_keys):.1%}。")
    ap("")
    ap("## ② 仅第一轨有的（学科, 档位, 院校）")
    ap("")
    if only_md:
        for d, g, ss in only_md:
            ap(f"- **{d} / {g}**：{'、'.join(ss)}（{len(ss)} 所）")
    else:
        ap("- 无")
    ap("")
    ap("## ③ 仅第二轨有的（学科, 档位, 院校）")
    ap("")
    if only_csv:
        for d, g, ss in only_csv:
            ap(f"- **{d} / {g}**：{'、'.join(ss)}（{len(ss)} 所）")
    else:
        ap("- 无")
    ap("")
    ap("## ④ 档位冲突（同学科同院校，两轨档位不同）")
    ap("")
    if conflicts:
        ap("| 学科 | 院校 | 第一轨档位 | 第二轨档位 |")
        ap("| --- | --- | --- | --- |")
        for d, s, g1, g2 in conflicts:
            ap(f"| {d} | {s} | {'/'.join(g1) or '—'} | {'/'.join(g2) or '—'} |")
    else:
        ap("- 无")
    ap("")
    ap("## 存疑（转录时原样保留，未做臆断）")
    ap("")
    ap("1. **统计学 页界档位**：图 (7) 统计学 A 档行列 5 所（北京师范大学、东北财经大学、东北师范大学、复旦大学、南开大学）；图 (8) 首行显式标注「A-」并列 8 所（江西财经大学、上海财经大学、上海交通大学、西南财经大学、云南大学、浙江工商大学、中国科学技术大学、中山大学）。第二轨按图面原样转录为 A/A- 两档；第一轨将该 8 所并入 A 档（无 A- 行）。此为两轨唯一实质分歧，需后续对照原图裁定。")
    ap("2. **安全科学与工程 A-**：图 (14) 源表中「山东科技大学」出现两次，第二轨照录两行，集合比对时折叠。")
    ap("3. **作物学 A-**：图 (15) 源表中「山东农业大学」出现两次，第二轨照录两行，集合比对时折叠。")
    ap("4. **工商管理 A- 截断**：图 (18) 截图在「山东大学」处结束，该行可能尚有院校未捕获，两轨同样不完整。")
    ap("5. 本次转录未发现局部模糊到无法辨认的行；如复核时发现，应补记本节。")
    ap("")
    ap("## 颜色观察（未核验元数据，绝不作为事实使用）")
    ap("")
    ap("原表院校名带文字颜色，疑似标注相对第四轮的变化，含义未经证实。逐图转录过程中的粗略观察：")
    ap("")
    ap("- **红色**：占绝大多数（各页主体），无法逐一枚举。")
    ap("- **蓝色**：较常见，散布于多页多个学科。")
    ap("- **绿色**（少量示例）：图 (2) 湘潭大学（马克思主义理论）、首都师范大学（马克思主义理论）；图 (3) 上海体育大学、首都师范大学；图 (5) 首都师范大学、湘潭大学、山西大学；图 (6) 南京信息工程大学；图 (7) 云南大学；图 (15) 南京林业大学、华南农业大学、上海海洋大学；图 (16) 宁波大学、南京医科大学；图 (17) 南京医科大学、北京协和医学院、海军军医大学；图 (18) 南京医科大学。")
    ap("- **黑色**（少量示例）：图 (1) 东北财经大学、西南政法大学；图 (2) 天津师范大学、中南民族大学、山东师范大学。")
    ap("")
    ap("以上颜色仅为观察记录，不写入 CSV，不参与任何入库决策。")
    ap("")

    OUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # 控制台摘要
    print(f"groups: total={len(all_keys)} identical={len(identical)} "
          f"diff={len(all_keys) - len(identical)}")
    print(f"only_md entries: {sum(len(ss) for _, _, ss in only_md)}")
    print(f"only_csv entries: {sum(len(ss) for _, _, ss in only_csv)}")
    print(f"grade conflicts: {len(conflicts)}")
    for d, g, ss in only_md:
        print(f"  only_md: {d}/{g}: {len(ss)}")
    for d, g, ss in only_csv:
        print(f"  only_csv: {d}/{g}: {len(ss)}")
    for d, s, g1, g2 in conflicts:
        print(f"  conflict: {d} {s}: {'/'.join(g1)} vs {'/'.join(g2)}")


if __name__ == "__main__":
    main()
