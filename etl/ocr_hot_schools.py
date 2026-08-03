"""
OCR 解析「热门大学介绍」目录下的「每日一校」卡片图，提取结构化字段并写入 school_hot_profiles 表。

目录结构：2026allmaterial/热门大学介绍/<分类>/<校名>.png
分类：985 / 211 / C9 / E9 / 双一流 / 五院四系 / 两电一邮 / 国防七子 / 八大美院

同一所学校可能出现在多个分类目录（如清华在 985/211/C9/双一流），内容相同。
本脚本按「校名」去重，仅解析首次出现的图，并把所有出现过的分类合并为 categories 标签。

用法：
    python etl/ocr_hot_schools.py           # 导入 DB
    python etl/ocr_hot_schools.py --dry-run # 仅解析并在本地打印，不写库
    python etl/ocr_hot_schools.py --limit 5 # 只处理前 N 所（按去重后顺序）
"""
import os
import re
import sys
import glob
import argparse
import subprocess
import psycopg2

BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "2026allmaterial", "热门大学介绍")
CATEGORIES = ["985", "211", "C9", "E9", "双一流", "五院四系", "两电一邮", "国防七子", "八大美院"]


def ocr_image(path):
    """用 tesseract 做中英文 OCR，返回纯文本。"""
    out = subprocess.run(
        ["tesseract", path, "stdout", "-l", "chi_sim+eng"],
        capture_output=True, text=True,
    )
    return out.stdout


# 区块标签：映射字段 -> 模糊匹配关键词（容忍 OCR 噪声）
BLOCK_LABELS = {
    "建校时间": ["建校时间"],
    "所在地区": ["所在地区", "所在地", "学校地址"],
    "办学性质": ["办学性质"],
    "升学率": ["升学率"],
    "院校类型": ["院校类型"],
    "保研率": ["保研率"],
    "硕博点": ["硕博点"],
    "学校排名": ["学校排名"],
    "院校简介": ["院校简介", "院校概况"],
    "学科评估": ["学科评估", "学科建设"],
    "特色专业": ["特色专业", "王牌专业"],
    "所获荣誉": ["所获荣誉", "所获荣"],
    "师资配备": ["师资配备"],
}

# 所有「区块标签」关键词，用于 block_value 确定内容边界
BLOCK_ALL = []
for _v in BLOCK_LABELS.values():
    BLOCK_ALL += _v
BLOCK_ALL += ["校园风采", "硕博点"]


def _find_label(lines, keywords):
    """返回第一个匹配关键词（含噪声容忍）的行索引，否则 -1。"""
    for i, ln in enumerate(lines):
        clean = re.sub(r"[\s|丨:：.·]", "", ln)
        for kw in keywords:
            ck = re.sub(r"[\s|丨:：.·]", "", kw)
            if ck and ck in clean:
                return i
    return -1


def parse_fields(text):
    """从 OCR 文本中按区块标签提取结构化字段。

    兼容两套「每日一校」模板：
      模板A（标准卡）：建校时间/所在地/性质/升学率/保研率/硕博点/排名/院校简介/学科评估/特色专业
      模板B（概况卡）：院校概况/学科建设/学校地址/王牌专业/所获荣誉/师资配备（年份/性质等常嵌在顶部无标签行）
    """
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    blob = "\n".join(lines)

    def same_line_value(label_idx):
        """标签行内冒号后的内容（如 '建校时间: 1911年'）。"""
        if label_idx < 0:
            return None
        ln = lines[label_idx]
        m = re.search(r"[:：]\s*(.+)$", ln)
        if m and m.group(1).strip():
            return m.group(1).strip()
        return None

    def single_value(label):
        """在整段文本中用正则提取『label: 值』，值截止到下一个同行标签或行尾。
        容忍 OCR 噪声（”等分隔符），兼容『建校时间: 1911年”所在地区: 北京』同行多标签。"""
        # 尝试该字段的每一个关键词（如 所在地区/所在地/学校地址）
        for kw in BLOCK_LABELS[label]:
            colon_others = [o for o in ("建校时间", "所在地区", "办学性质", "升学率", "院校类型", "保研率") if o != label]
            bare_others = [o for o in ("硕博点",) if o != label]
            ahead = "|".join(colon_others)
            bare = "|".join(bare_others)
            pat = rf"{kw}\s*[:：]\s*(.+?)(?=\s*(?:{ahead})\s*[:：]|\s*(?:{bare})\b|$)"
            m = re.search(pat, blob, re.DOTALL)
            if m:
                v = re.sub(r"\s+", " ", m.group(1)).strip().strip("”\"' ")
                if v:
                    return v
        return None

    def block_value(label):
        """标签独占一行，内容到下一个区块标签或『校园风采』为止。"""
        idx = _find_label(lines, BLOCK_LABELS[label])
        if idx < 0:
            return None
        end = len(lines)
        for j in range(idx + 1, len(lines)):
            clean = re.sub(r"[\s|丨:：.·]", "", lines[j])
            if clean in [re.sub(r"[\s|丨:：.·]", "", b) for b in BLOCK_ALL]:
                end = j
                break
        chunk = " ".join(lines[idx + 1:end]).strip()
        return chunk or None

    # 校名：第一个「XX大学/学院」且无标签前缀的行
    name = None
    for ln in lines:
        m = re.match(r"^(.*?(大学|学院|分校))", ln)
        if m:
            cand = m.group(1).strip()
            if not re.match(r"^(建校时间|所在地区?|办学性质|升学率|保研率|院校类型|硕博点|博士点|学校排名|院校简介|院校概况|学科评估|学科建设|特色专业|王牌专业|所获荣)", cand):
                name = cand
                break

    # 硕博点：标签行后下一行取前两个数字
    mp = dp = None
    mi = _find_label(lines, BLOCK_LABELS["硕博点"])
    if mi >= 0 and mi + 1 < len(lines):
        nums = re.findall(r"\d+", lines[mi + 1])
        if len(nums) >= 1:
            mp = int(nums[0])
        if len(nums) >= 2:
            dp = int(nums[1])

    def to_int(v):
        if not v:
            return None
        m = re.search(r"\d+", v)
        return int(m.group()) if m else None

    established = to_int(single_value("建校时间"))
    # 模板B fallback：顶部无标签行如 '1952年  公办  综合  教育部'
    if established is None:
        for ln in lines:
            if re.search(r"\d{4}年", ln) and re.search(r"(公办|综合|理工|教育部|师范|医药|农林|财经|语言|艺术|民族)", ln):
                m = re.search(r"(\d{4})年", ln)
                if m:
                    established = int(m.group(1))
                    break

    return {
        "name": name,
        "established": established,
        "location": single_value("所在地区"),
        "nature": single_value("办学性质"),
        "school_type": single_value("院校类型"),
        "upgrade_rate": single_value("升学率"),
        "grad_recommend_rate": single_value("保研率"),
        "master_points": mp,
        "doctor_points": dp,
        "ranking": block_value("学校排名") or same_line_value(_find_label(lines, BLOCK_LABELS["学校排名"])),
        "intro": block_value("院校简介"),
        "discipline_eval": block_value("学科评估"),
        "features": block_value("特色专业"),
        "honors": block_value("所获荣誉"),
        "faculty": block_value("师资配备"),
    }


def collect():
    """收集所有图，按校名去重，记录分类标签与首个图路径。"""
    seen = {}  # name -> {'cats':[], 'path':}
    order = []
    for cat in CATEGORIES:
        d = os.path.join(BASE, cat)
        if not os.path.isdir(d):
            continue
        for fp in sorted(glob.glob(os.path.join(d, "*.png"))):
            name = os.path.splitext(os.path.basename(fp))[0]
            if name not in seen:
                seen[name] = {"cats": [cat], "path": fp}
                order.append(name)
            else:
                if cat not in seen[name]["cats"]:
                    seen[name]["cats"].append(cat)
    return [(n, seen[n]) for n in order]


def ensure_table(conn):
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS school_hot_profiles (
            code text,
            name text,
            categories text[],
            established integer,
            location text,
            nature text,
            school_type text,
            upgrade_rate text,
            grad_recommend_rate text,
            master_points integer,
            doctor_points integer,
            ranking text,
            intro text,
            discipline_eval text,
            features text,
            honors text,
            faculty text,
            image_path text
        )
    """)
    conn.commit()


def lookup_code(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT code FROM schools WHERE name=%s", (name,))
    r = cur.fetchone()
    if r:
        return r[0]
    # 部分图名可能带括号差异，模糊匹配
    cur.execute("SELECT code,name FROM schools WHERE name LIKE %s", (name[:4] + "%",))
    for code, n in cur.fetchall():
        if name in n or n in name:
            return code
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    items = collect()
    print(f"去重后院校数: {len(items)}")

    conn = None
    if not args.dry_run:
        import os as _os
        dsn = _os.environ.get("GAOKAO_DSN")
        if not dsn:
            print("缺少 GAOKAO_DSN，dry-run 模式退出")
            args.dry_run = True
        else:
            conn = psycopg2.connect(dsn)
            try:
                ensure_table(conn)
            except psycopg2.errors.InsufficientPrivilege:
                # 表可能已由超级用户预先建好，跳过建表
                conn.rollback()

    processed = 0
    for name, info in items:
        if args.limit and processed >= args.limit:
            break
        text = ocr_image(info["path"])
        fields = parse_fields(text)
        if not fields["name"]:
            fields["name"] = name
        fields["categories"] = info["cats"]
        fields["image_path"] = info["path"]

        if args.dry_run:
            print("=" * 60)
            print(f"【{name}】 分类: {info['cats']}  图: {os.path.basename(info['path'])}")
            for k, v in fields.items():
                if k not in ("name", "categories", "image_path"):
                    sval = (v[:60] + "…") if isinstance(v, str) and len(v) > 60 else v
                    print(f"  {k}: {sval}")
        else:
            code = lookup_code(conn, name)
            cur = conn.cursor()
            cur.execute("DELETE FROM school_hot_profiles WHERE name=%s", (name,))
            cur.execute(
                """INSERT INTO school_hot_profiles
                   (code,name,categories,established,location,nature,school_type,
                    upgrade_rate,grad_recommend_rate,master_points,doctor_points,
                    ranking,intro,discipline_eval,features,honors,faculty,image_path)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (code, name, info["cats"], fields["established"], fields["location"],
                 fields["nature"], fields["school_type"], fields["upgrade_rate"],
                 fields["grad_recommend_rate"], fields["master_points"], fields["doctor_points"],
                 fields["ranking"], fields["intro"], fields["discipline_eval"],
                 fields["features"], fields["honors"], fields["faculty"], info["path"]),
            )
            conn.commit()
        processed += 1

    if conn:
        conn.close()
    print(f"\n完成，处理 {processed} 所（去重后）")


if __name__ == "__main__":
    main()
