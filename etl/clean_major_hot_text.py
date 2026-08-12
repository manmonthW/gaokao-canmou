#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
clean_major_hot_text.py —— major_hot_profiles 文字系统清洗（幂等，可重跑）

背景：专业详情抽屉（MajorDrawer）文字来自两路：1936 页 PDF 文本抽取
（ocr_major_intros.py）与 78 张热门专业 PNG 的 OCR（ocr_hot_majors.py）。
页面曾出现：① 大量「暂无」占位区块；②「暂无+XX类」粘行污染；③ PNG 图表区
垃圾（薪资范围/学历要求/趋势图…）混入「就业前景」；④ 图片 OCR 折行空格把
句子切断；⑤ 个别字段间内容完全重复。本脚本做数据级系统清洗。

规则（全部幂等）：
1. 占位值 {暂无,无,暂无。,无。,略,-,—,N/A} → NULL（前端 v-if 自动隐藏区块）；
2. social_celebrities 形如「暂无…类」的粘行污染 → NULL；
3. career 在首个图表垃圾标记处截断，截断后做折行合并，长度<25 → NULL；
4. career/employment_dir/subject_req 在首个「类目 chip」串处截断（PNG OCR 图表
   残留，如 生物/制药/医疗、财务/审计/税务），尾段非完整句时补「等。」；
5. career 与 employment_dir 内容包含/重复（语义重复且前端已隐藏 career）→ NULL；
6. 全部文本字段做「汉字+空白+汉字」折行合并（含换行），消除 OCR 断行；
7. OVERRIDES：逐专业核对发现的人工修正（字段置 NULL 或替换文本）。

用法：
  python3 etl/clean_major_hot_text.py            # 仅打印变更报告
  python3 etl/clean_major_hot_text.py --apply    # 报告并写库（单事务）
"""
import os
import re
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import psycopg2
from config import DSN

FIELDS = ["introduction", "subject_req", "career", "training_goal", "discipline_req",
          "main_courses", "postgrad_dir", "employment_dir", "training_req",
          "knowledge_ability", "social_celebrities"]

PLACEHOLDERS = {"暂无", "无", "暂无。", "无。", "略", "-", "—", "N/A"}

# career（PNG OCR）图表区垃圾标记：正文结束、图表文字开始的特征串
GARBAGE_MARKERS = ["薪资范围", "学历要求", "近12个月", "元/月", "占比",
                   "质量安全", "生产/营运", "电子/电器", "就业 就业",
                   "招聘薪资趋势", "趋势图", "赵势图", "招聘学习要求",
                   "就业占比"]

# 类目 chip：PNG 图表里的行业/职能类目串，混入正文尾部
CHIP_RE = re.compile(r"(生物/制药/医疗|医院/医疗/护理|电子/电器/仪器|财务/审计/税务|"
                     r"行政/后勤|金融/证券/期货|销售行政及商务|运维/技术支持|"
                     r"客服支持人力资源|客服支持行政/后勤)")

# 需要 chip 截断的字段
CHIP_FIELDS = {"career", "employment_dir", "subject_req"}

# 折行合并：汉字之间夹空白（空格/换行）一律粘连；循环到稳定以处理连续多行
CJK_WRAP = re.compile(r"([一-鿿])\s+([一-鿿])")

# 粘行污染：「暂无」后粘上下一节类目行（XX类）
GLUED_NONE = re.compile(r"^暂无[^，。；]{0,12}类$")

# 尾部粘行：正文句末后粘上类目行（如 名人列表后粘「统计学类」）
GLUED_TAIL = re.compile(r"。[^。；，]{1,14}类$")

# 系统性 OCR 错字（全局替换，幂等）
TYPO_FIXES = [("-定的", "一定的"), ("土要学习", "主要学习"), ("罗辑思维", "逻辑思维"),
              ("先择升学", "选择升学"), ("景重要的", "最重要的"), ("工业主产", "工业生产"),
              ("广矿企业", "厂矿企业"), ("内性格上", "性格上"), ("信息的7.基本方法", "信息的基本方法"),
              ("典入式", "嵌入式"), ("学本专业学生", "本专业学生"), ("相互作巴", "相互作用，将"),
              ("工悍师", "工程师")]

# 选科/学科要求尾部截断修复（PDF 列宽截断，尾部固定句式可安全补全）
TRUNC_APPEND = [("的学生就", "的学生就读。"), ("感兴趣", "感兴趣的学生就读。"),
                ("有兴趣", "有兴趣的学生就读。"), ("的学", "的学生就读。"),
                ("的学生", "的学生就读。"), ("热爱", "热爱的学生就读。")]

# 句子型字段：尾部缺句号时补「。」
SENTENCE_FIELDS = {"introduction", "training_goal", "training_req", "knowledge_ability", "employment_dir"}

# ---------- 逐专业核对人工修正（发现即追加，保持幂等） ----------
# 值为 None 表示该字段置 NULL；字符串表示替换
OVERRIDES = {
    # introduction 与 training_goal 完全相同（PDF 同源重复）：保留 introduction
    "遥感科学与技术": {"training_goal": None},
    # employment_dir 与 training_req 完全相同：保留 employment_dir
    "香料香精技术与工程": {"training_req": None},
    # OCR 误字/断句修正
    "医学影像学": {
        "introduction": "医学影像学是研究借助于某种介质（如X射线、电磁场、超声波等）与人体相互作用，将人体内部组织器官结构、密度以影像方式表现出来，供诊断医师根据影像提供的信息进行判断，从而对人体健康状况进行评价的一门科学，包括医学成像系统和医学图像处理两方面相对独立的研究方向。",
        "postgrad_dir": "影像医学与核医学、临床医学、外科学",
        "employment_dir": "本专业就业前景很好，毕业生主要从事临床医学影像诊断或放射治疗工作或医学教育及医学科研工作，也可到医疗卫生单位从事医学影像诊断、介入放射学、核医学成像技术等方面的工作。",
    },
    "审计学": {
        "career": "审计专员/助理、公务员（中央国家机关）、公务员（省级机关）、公务员（地市级机关）、公务员（县级及以下机关）、公司业务、事业单位人员、出纳员、财务助理、会计/会计师。",
    },
    "应用化学": {
        "career": "应用化学专业的毕业生一次性就业率比较高，就业行业包括教育、材料、军工、汽车、军队、电子、信息、环保、市政、建筑、建材、消防、化工、机械等；就业单位包括各级质量监督与检测部门、科研院所、设计院所、教学单位、生产企业、省级以上的消防部门等。",
        "subject_req": "一般选考要求物理+化学，该专业对化学科目要求较高。该专业适合喜欢化学、乐于科学研究的学生就读。",
    },
    "应用心理学": {
        "career": "应用心理学专业可在学校、机关、社区、企业、医疗卫生、监狱、行政管理等部门从事教学、管理、咨询、技术研发等工作，还可开办社会心理咨询机构、儿童成长工作室等进行自主创业。相关职业资格有中小学教师资格证、国家心理咨询师、婚姻家庭师等。",
        # subject_req 尾部截断，按 discipline_req 完整句补全；随后 discipline_req 为其子集，置 NULL
        "subject_req": "一般选考要求不限，该专业对心理学科目要求较高。该专业适合对人文社会科学有兴趣，同时热爱心理学的学生就读。",
        "discipline_req": None,
    },
    "法学": {
        "career": "法学专业学生毕业后，适合从事审判、检察、司法行政、律师、公安等实际工作，也可从事立法、法学教育、法学研究以及行政管理和公司、企业的法律顾问等工作。",
    },
    "生物科学": {
        "career": "农、林、牧、渔类企业：生物研究、生物技术、生产管理、技术开发；医药类企业：生物工程、生物制药、生化实验；教育类企业：生物教师、生物产品经营等。",
        "subject_req": "一般选考要求物理+化学，该专业对生物科目要求较高。该专业适合对自然科学感兴趣、热爱生物科学的学生就读。",
        "discipline_req": "该专业对生物科目要求较高。该专业适合对自然科学感兴趣、热爱生物科学的学生就读。",
    },
    "材料科学与工程": {
        "career": "材料科学与工程专业毕业生可在新型能源材料、新型功能材料、生态环境材料、复合材料、高分子材料等行业和相关部门从事生产技术、材料开发、质量管理、技术管理及产品营销等工作；也可在科研机构、高等院校、质量检验、商检等部门从事材料科学方面的科研和管理工作。",
    },
    "金融学": {
        "career": "金融学专业毕业生就业主要面向银行及金融系统。除了商业银行、股份制商行、外资银行驻国内分支机构以外，还有几大主要去向：金融业监督管理机构；证券公司；四大会计师事务所；保险公司、社保基金管理中心或社保局；上市（拟上市）股份公司证券部、财务部、证券事务代表等；国家公务员序列的政府行政机构如财政、审计、海关部门等。",
    },
    "网络空间安全": {
        "introduction": "该专业为新增专业。网络空间安全指网络空间面临的所有安全问题，即网络复杂性、信息涉及面的广泛性、隐性连接性、隐含性。",
        "subject_req": "该专业对计算机要求较高。该专业适合对网络空间安全感兴趣的学生就读。",
        "training_goal": "培养具有扎实的网络空间安全基础理论和基本技术，系统掌握网络安全技术、网络安全法律、网络安全管理的专业知识，政治过硬，较强的中英文沟通和写作能力，有技术，懂法律，会谈判的复合型人才。",
        "employment_dir": "网络空间安全人才分布在网络与网络安全保障的各个领域，该专业毕业生毕业后可从事于国家、政法、企业和个人的网络空间安全保障和治理的相关工作。",
        # discipline_req 与 subject_req 完全相同：保留 subject_req
        "discipline_req": None,
    },
    "统计学": {
        "subject_req": "一般选考要求物理+化学，该专业对数学科目要求较高。该专业适合对逻辑推理有兴趣，喜爱数理统计的学生就读。",
        "knowledge_ability": "1.掌握数学、物理的基础知识，具有较强的分析和演算能力； 2.掌握统计学的基本理论和方法，能熟练运用计算机分析数据； 3.了解相近专业的一般原理和知识； 4.了解统计学理论前沿与发展动态； 5.掌握文献检索、资料查询的基本方法，具有一定的科学研究和实际工作能力。",
    },
    "小学教育": {
        "introduction": "小学教育面向全体适龄儿童，任何未成年的公民，不论其种族、民族、性别、肤色、语言、社会经济地位的差异（智能及身体状况不允许的例外），只要达到一定的年龄（6～12岁），都必须接受小学教育。",
        "employment_dir": "小学教育的就业面比较宽，主要从事小学教育机构的教学工作，或者如果自己的交际能力比较强的话也可以从事咨询方面的工作，此外还可从事教师、教育咨询、编辑出版等工作。",
    },
    "麻醉学": {
        "introduction": "麻醉学是一门研究临床麻醉、生命机能调控、疼痛诊疗的科学，通常在手术或急救过程中应用。",
        "subject_req": "该专业对生物科目要求较高。该专业适合对手术麻醉处理、围麻醉期并发症防治和危重病症监测、判断和治疗感兴趣的学生就读。",
        "training_goal": "本专业培养具有基础医学、临床医学和麻醉学等方面的基本理论知识和基本技能，能在医疗卫生单位的麻醉科、急诊科、急救中心、重症监测治疗病房（ICU）、药物依赖戒断及疼痛诊疗等领域从事临床麻醉、急救和复苏、术后监测、生理机能调控等方面工作的医学高级专门人才。",
        "employment_dir": "毕业生主要到医疗卫生单位的麻醉科、急诊科、急救中心、重症监测治疗病房、药物依赖戒断及疼痛诊疗等领域从事临床麻醉、急救和复苏、术后监测、生理机能调控等方面的工作。",
        # discipline_req 与 subject_req 完全相同：保留 subject_req
        "discipline_req": None,
    },
    "历史学": {
        "subject_req": "一般选考要求不限，该专业对历史、政治科目要求较高。该专业适合喜欢历史研究、喜欢自然人文社科的学生就读。",
        "career": None,
    },
    # introduction 首句整句重复：去重
    "农业智能装备工程": {
        "introduction": "本专业属于新农科工程类专业，是农业工程与机械工程、农学与生命科学、信息科学等学科深度交叉融合的产物，是融合新一代信息技术，对现有农业工程、农业机械化及其自动化等专业的拓展和延伸。",
    },
    # ---------- career（PNG OCR）尾部图表垃圾无法规则截断，且就业方向已有干净文本 ----------
    "地理科学": {
        "career": None,
        "subject_req": "一般选考要求物理+化学，该专业对地理科目要求较高。该专业适合对自然科学感兴趣、热爱地理科学的学生就读。",
    },
    "数学与应用数学": {
        "career": None,
        "subject_req": "一般选考要求物理+化学，该专业对数学科目要求较高。该专业适合逻辑思维严密、善于思考的学生就读。",
    },
    "数据科学与大数据技术": {"career": None},
    "机械工程": {"career": None},
    "物理学": {"career": None},
    "电子信息科学与技术": {"career": None},
    "网络与新媒体": {
        "career": None,
        "knowledge_ability": "1.掌握网络与新媒体的基本知识和理论； 2.了解网络与新媒体发展动态； 3.了解网络与新媒体的方针、政策和法规； 4.了解本学科的前沿成就和发展前景； 5.能阅读古典文献，掌握文献检索、资料查询的基本方法，具有一定的科学研究和实际工作能力。",
    },
    "信息与计算科学": {"career": None},
    # ---------- 选科要求 OCR 粘行/截断，规则无法修复 ----------
    "化学": {
        "subject_req": "一般选考要求物理+化学，该专业对化学科目要求较高。该专业适合化学基础知识扎实、喜欢化学研究的学生就读。",
    },
    "电子信息工程": {
        "subject_req": "一般选考要求物理+化学，该专业对物理科目要求较高。该专业适合对电子信息技术及信息系统感兴趣的学生就读。",
    },
    "自动化": {
        "subject_req": "一般选考要求物理+化学，该专业对物理科目要求较高。该专业适合对自动化技术感兴趣、热爱信号控制的学生就读。",
    },
    "通信工程": {
        "subject_req": "一般选考要求物理+化学，该专业对物理科目要求较高。该专业适合对通信应用感兴趣，善于分析与设计的学生就读。",
    },
    "机械电子工程": {
        "subject_req": "一般选考要求物理+化学，该专业对数学、物理科目要求较高。该专业适合对机械有兴趣、善于电子技术的学生就读。",
    },
    # discipline_req 尾部残句（以逗号结束）且 subject_req 为空：改写后移入 subject_req
    "金融科技": {
        "subject_req": "该专业对数学科目要求较高。该专业适合对经济金融研究、国内外金融发展的高新技术感兴趣的学生就读。",
        "discipline_req": None,
    },
}


def join_wraps(s: str) -> str:
    prev = None
    while prev != s:
        prev = s
        s = CJK_WRAP.sub(r"\1\2", s)
    return s


def clean_career(s: str):
    """截断图表垃圾并合并折行；返回 (新值, 是否截断)。
    错字修正在折行合并之后再跑一遍：OCR 把错字拆开（如「典 入式」）时，
    合并前 replace 会漏掉，合并后才能命中。"""
    cut = min((s.find(m) for m in GARBAGE_MARKERS if s.find(m) >= 0), default=-1)
    truncated = cut >= 0
    if truncated:
        s = s[:cut]
    s = fix_typos(join_wraps(s).strip())
    return s, truncated


def fix_typos(s: str) -> str:
    for bad, good in TYPO_FIXES:
        s = s.replace(bad, good)
    return s


def repair_subj_trunc(s: str) -> str:
    """选科/学科要求尾部截断补全（固定句式）。"""
    for pat, rep in TRUNC_APPEND:
        if s.endswith(pat):
            return s + rep[len(pat):]
    if s.endswith("要求较") or s.endswith("要求较 ".strip()):
        return s + "高。"
    return s


def char_overlap(a: str, b: str) -> float:
    """两文本去重字符集的 Jaccard 相似度（用于识别同源重复）。"""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def cut_chips(s: str) -> str:
    """在首个类目 chip 处截断；尾段为残句时回退到上一完整句或补「等。」。"""
    m = CHIP_RE.search(s)
    if not m:
        return s
    s = s[:m.start()].rstrip(" 、，,;；")
    s = s.rstrip("等")
    if s and s[-1] not in "。！？；":
        # 回退：若 chip 前残句较长且存在更早的完整句，直接取到完整句末
        prev = max(s.rfind("。"), s.rfind("！"), s.rfind("？"))
        if prev >= 0 and len(s) - prev - 1 > 15:
            s = s[:prev + 1]
        else:
            s += "等。"
    return s


def transform(row: dict) -> dict:
    """对一行做全部规则变换，返回新值字典（仅含变化字段）。"""
    changed = {}
    for f in FIELDS:
        old = row.get(f)
        if old is None:
            new = None
        else:
            new = fix_typos(old.strip())
            if f == "career":
                new, _ = clean_career(new)
                new = cut_chips(new)
                if len(new) < 25:
                    new = None
                else:
                    ed = (row.get("employment_dir") or "").strip()
                    # 与就业方向内容包含/重复（同源），且前端已不单列 career
                    if ed and (new in ed or ed in new or char_overlap(new, ed) > 0.7):
                        new = None
            elif new in PLACEHOLDERS:
                new = None
            elif f == "social_celebrities":
                if GLUED_NONE.match(new):
                    new = None
                else:
                    new = GLUED_TAIL.sub("。", new)
            else:
                if f in CHIP_FIELDS:
                    new = cut_chips(new)
                # 折行合并后再跑一次错字修正（拆开的错字合并后才能命中）
                new = fix_typos(join_wraps(new))
                if new in PLACEHOLDERS:
                    new = None
                else:
                    if f in ("subject_req", "discipline_req"):
                        new = repair_subj_trunc(new)
                    elif f in SENTENCE_FIELDS and new and (new[-1].isalnum() or "一" <= new[-1] <= "鿿"):
                        new += "。"
        # 人工修正优先
        ov = OVERRIDES.get(row["name"], {}).get(f, "__NO__")
        if ov != "__NO__":
            new = ov
        if new != old:
            changed[f] = new
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    conn = psycopg2.connect(DSN)
    cur = conn.cursor()
    cur.execute(f"SELECT name, {', '.join(FIELDS)} FROM major_hot_profiles ORDER BY name")
    rows = cur.fetchall()

    n_null = {f: 0 for f in FIELDS}
    n_join = 0
    n_rows = 0
    updates = []
    for r in rows:
        row = {"name": r[0]}
        for i, f in enumerate(FIELDS, 1):
            row[f] = r[i]
        changed = transform(row)
        if not changed:
            continue
        n_rows += 1
        for f, v in changed.items():
            if v is None and row[f] is not None:
                n_null[f] += 1
            elif v is not None and row[f] is not None and v != row[f]:
                n_join += 1
        updates.append((row["name"], changed))

    print(f"扫描 {len(rows)} 行，需变更 {n_rows} 行")
    print("置 NULL 统计（按字段）:")
    for f in FIELDS:
        if n_null[f]:
            print(f"  {f:20s} {n_null[f]}")
    print(f"折行合并/文本替换: {n_join} 处")

    if args.apply and updates:
        for name, changed in updates:
            sets = ", ".join(f"{f}=%s" for f in changed)
            vals = [changed[f] for f in changed] + [name]
            cur.execute(
                f"UPDATE major_hot_profiles SET {sets} WHERE name=%s", vals)
        conn.commit()
        print(f"已写库：{len(updates)} 行更新（单事务）")
    elif not args.apply:
        print("（加 --apply 写库）")
        # 抽样展示前 5 行变更
        for name, changed in updates[:5]:
            print(f"  例 {name}: " + ", ".join(f"{k}->{(v or 'NULL')[:30]!r}" for k, v in list(changed.items())[:3]))
    conn.close()


if __name__ == "__main__":
    main()
