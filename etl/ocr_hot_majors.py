"""
OCR 热门专业盘点 PNG 图片，提取结构化文本，存入 major_hot_profiles 表。

图片来源: 2026allmaterial/热门专业盘点/
- 78张竖图 (840x2250左右)，每张包含一个专业的详细介绍
- 两种模板格式（旧版/新版），字段略有不同
- 用 tesseract(chi_sim+eng) 做 OCR，再用正则结构化提取

输出: major_hot_profiles 表
  - code -> major_catalog.code (外键)
  - name, degree, length, gender_ratio
  - introduction, subject_req, career, training_goal,
    discipline_req, main_courses, postgrad_dir, employment_dir,
    hot_schools (text[])
  - image_path (原始PNG路径)
"""
import os
import re
import subprocess
import sys

# 添加 backend 路径以便 import db
sys.path.insert(0, "/home/ekewang/projects/gaokao/ln/webapp/backend")

MATERIAL_DIR = "/home/ekewang/projects/gaokao/ln/2026allmaterial/热门专业盘点"


def ocr_image(filepath: str) -> str:
    """对单张 PNG 执行 tesseract OCR，返回纯文本。"""
    result = subprocess.run(
        ["tesseract", filepath, "stdout", "-l", "chi_sim+eng"],
        capture_output=True, text=True, timeout=30,
    )
    return result.stdout


def parse_ocr_text(text: str, name: str) -> dict:
    """从 OCR 文本中用正则提取结构化字段。

    兼容两种模板:
      旧版: 专业介绍 | 选科要求 | 就业前景 | 开设院校
      新版: 培养目标 | 学科要求 | 主要课程 | 考研方向 | 就业方向 | 开设院校
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()]
    full = "\n".join(lines)

    result = {
        "name": name,
        "degree": None,       # 授予学位
        "length": None,       # 学制年限
        "gender_ratio": None, # 男女比例
        "introduction": None, # 专业介绍
        "subject_req": None,  # 选科要求
        "career": None,       # 就业前景(旧版)
        "training_goal": None,# 培养目标(新版)
        "discipline_req": None, # 学科要求(新版)
        "main_courses": None, # 主要课程(新版)
        "postgrad_dir": None, # 考研方向(新版)
        "employment_dir": None, # 就业方向(新版)
        "hot_schools": [],     # 开设院校列表
    }

    # --- 头部信息行（学位/学制/男女比例）---
    # 格式如: "本科    四年    工学学士    63:37" 或 "专业学制: 四年  授予学位: 工学或理学学士"
    m = re.search(r"授予学位[：:]\s*(.+?)(?:\n|$)", full)
    if m:
        result["degree"] = clean(m.group(1))
    else:
        # 新版格式: 在头部行找 "学士"/"硕士"
        for line in lines[:8]:
            if "学士" in line or "硕士" in line:
                m2 = re.search(r"(?:理学|工学|医学|文学|经济学|管理学|法学|教育学|历史学|农学|哲学|艺术学)\s*[学士硕士]+", line)
                if m2:
                    result["degree"] = m2.group(0)
                    break

    m = re.search(r"(?:学制|修业年限)[：:]\s*(\d+)\s*年?", full)
    if m:
        result["length"] = int(m.group(1))
    else:
        # 头部行可能含 "四年制" / "X年制" / "本科四年"
        for line in lines[:10]:
            m2 = re.search(r"(\d+)\s*年制?", line)
            if m2:
                result["length"] = int(m2.group(1))
                break

    # 学位：优先 "授予学位：X学学士"；否则从头部找 "X学学士/硕士"
    m = re.search(r"授予学位[：:]\s*([\u4e00-\u9fff]+?(?:学士|硕士|博士))", full)
    if m:
        result["degree"] = m.group(1)
    else:
        for line in lines[:10]:
            m2 = re.search(r"([\u4e00-\u9fff]{2,4}?学?(?:学士|硕士|博士))", line)
            if m2 and ("学士" in m2.group(1) or "硕士" in m2.group(1)):
                result["degree"] = m2.group(1)
                break

    m = re.search(r"(\d{1,3})[：:](\d{1,3})", full)
    if m and ("男女" in full or "比例" in full):
        result["gender_ratio"] = f"{m.group(1)}:{m.group(2)}"

    # --- 段落字段提取 ---
    # 存在两种模板：
    #   旧版: 章节标题直接是文字 (专业介绍 / 选科要求 / 就业前景)，无竖线
    #   新版: 章节标题带竖线 (| 培养目标 / | 学科要求 / | 主要课程 / | 考研方向 / | 就业方向)
    # "专业介绍" 在旧版有标题，在新版无标题（头部后第一段）
    sections = {
        "专业介绍": "introduction",
        "选科要求": "subject_req",
        "就业前景": "career",
        "培养目标": "training_goal",
        "学科要求": "discipline_req",
        "主要课程": "main_courses",
        "考研方向": "postgrad_dir",
        "就业方向": "employment_dir",
    }

    SECTION_RE = re.compile(r"^\|?\s*(.+?)\s*$")

    def section_title_of(line: str):
        """若本行是章节标题，返回标题名，否则 None。兼容带/不带竖线前缀。"""
        if len(line) > 8:  # 章节标题通常较短
            return None
        m = SECTION_RE.match(line)
        if not m:
            return None
        title = m.group(1).strip()
        # 归一化：去掉可能多余的空格/符号
        for k in sections.keys():
            if title == k or title.replace(" ", "") == k:
                return k
        return None

    # 标记头部结束位置（找到第一个章节标题即为正文开始）
    body_start = len(lines)
    for i, line in enumerate(lines):
        if section_title_of(line):
            body_start = i
            break

    # 头部信息之后的段落（到第一个章节标题前）= 专业介绍（仅新版无标题时）
    intro_lines = []
    HEADER_RE = re.compile(r'(学历层次|修业年限|授予学位|男女比例|本科|专科|研究生|专业学制|学十|学土|学士|学制|助力高考|BSR)')
    for line in lines[:body_start]:
        if HEADER_RE.search(line):
            continue
        if len(line) > 8 and not re.match(r'^[\d\s%\.\-\|eaoeEAOE]+$', line):
            intro_lines.append(line)

    # 如果 introduction 还没被 sections 匹配到（新版情况），用头部后段落填充
    if not result["introduction"] and intro_lines:
        result["introduction"] = clean(" ".join(intro_lines))

    current_section = None
    section_lines = []

    def flush():
        nonlocal section_lines
        if current_section and section_lines:
            key = sections.get(current_section)
            if key and not result[key]:
                result[key] = clean(" ".join(section_lines))
        section_lines = []

    for line in lines[body_start:]:
        sec = section_title_of(line)
        if sec:
            flush()
            current_section = sec
        elif current_section:
            # 跳过图表区域的乱码行（太短、含特殊字符、纯数字百分比）
            if len(line) > 6 and not re.match(r'^[\d\s%\.\-\|eaoeEAOE]+$', line):
                section_lines.append(line)

    flush()

    # --- 开设院校（在文件末尾，通常是标签形式）---
    school_pattern = re.compile(
        r"(?:中国科学院大学|清华大学|北京大学|浙江大学|复旦大学|上海交通大学|"
        r"南京大学|中国科学技术大学|华中科技大学|武汉大学|西安交通大学|哈尔滨工业大学|"
        r"中山大学|北京师范大学|同济大学|南开大学|天津大学|国防科技大学|厦门大学|"
        r"山东大学|中南大学|大连理工大学|吉林大学|湖南大学|华东师范大学|华南理工大学|"
        r"电子科技大学|重庆大学|四川大学|东北大学|兰州大学|东南大学|北京航空航天大学|"
        r"北京理工大学|西北工业大学|中国农业大学|中央民族大学|中国海洋大学|"
        r"北京邮电大学|西安电子科技大学|北京交通大学|北京科技大学|南京航空航天大学|"
        r"南京理工大学|西南交通大学|河海大学|武汉理工大学|合肥工业大学|哈尔滨工程大学|"
        r"东华大学|江南大学|暨南大学|西南大学|长安大学|中国矿业大学|中国石油大学|"
        r"中国地质大学|东北师范大学|华中农业大学|华中师范大学|陕西师范大学|南京师范大学|"
        r"西南财经大学|中南财经政法大学|上海财经大学|对外经济贸易大学|中央财经大学|"
        r"北京外国语大学|上海外国语大学|中国政法大学|北京中医药大学|北京林业大学|"
        r"北京化工大学|北京体育大学|中国传媒大学|中央美术学院|中央音乐学院|"
        r"上海大学|苏州大学|郑州大学|福州大学|安徽大学|南昌大学|广西大学|贵州大学|"
        r"云南大学|海南大学|内蒙古大学|宁夏大学|青海大学|西藏大学|新疆大学|石河子大学|"
        r"山西大学|河北大学|河南大学|江苏大学|浙江工业大学|广东工业大学|深圳大学|"
        r"南方医科大学|首都医科大学|首都师范大学|北京工业大学|天津医科大学|"
        r"南方科技大学|上海科技大学|西湖大学)"
    )
    schools_found = school_pattern.findall(full)
    if schools_found:
        result["hot_schools"] = list(dict.fromkeys(schools_found))[:15]  # 去重+限数

    return result


def clean(s: str) -> str:
    """清理 OCR 噪声：去除多余空格、换行、乱码片段。"""
    s = re.sub(r'\s+', ' ', s).strip()
    # 去除常见的 OCR 乱码前缀
    for prefix in ['e ie Sz', 'ie Sz', 'ea', 'oe', 'BEAR', 'OO', 'ee']:
        if s.lower().startswith(prefix.lower()):
            s = s[len(prefix):].strip()
    return s


# ---- 主流程 ----
def main():
    import psycopg2
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from config import DSN as WRITE_DSN

    conn = psycopg2.connect(WRITE_DSN)
    conn.autocommit = True
    cur = conn.cursor()

    files = sorted([f for f in os.listdir(MATERIAL_DIR) if f.endswith(".png")])
    print(f"共发现 {len(files)} 张图片")

    results = []
    for i, fname in enumerate(files):
        # 从文件名提取专业名: （N）专业名.png
        m = re.match(r'（(\d+)）(.+?)\.png', fname)
        if not m:
            print(f"  跳过无法解析的文件名: {fname}")
            continue
        seq = int(m.group(1))
        name = m.group(2)

        fpath = os.path.join(MATERIAL_DIR, fname)
        print(f"[{i+1}/{len(files)}] ({seq}) {name} ... ", end="", flush=True)

        try:
            text = ocr_image(fpath)
            parsed = parse_ocr_text(text, name)
            parsed["seq"] = seq
            parsed["image_path"] = fpath
            results.append(parsed)
            has_content = sum(1 for k in ["introduction","subject_req","career","training_goal",
                                           "discipline_req","main_courses","employment_dir"]
                             if parsed[k])
            print(f"OK ({has_content}个字段)")
        except Exception as e:
            print(f"ERR: {e}")

    print(f"\nOCR 完成: {len(results)}/{len(files)}")

    # ---- 建表 ----
    cur.execute("""
        CREATE TABLE IF NOT EXISTS major_hot_profiles (
            id              SERIAL PRIMARY KEY,
            code            VARCHAR(20),
            name            VARCHAR(100) NOT NULL UNIQUE,
            seq             INT,
            degree          VARCHAR(50),
            length          INT,
            gender_ratio    VARCHAR(20),
            introduction    TEXT,
            subject_req     TEXT,
            career          TEXT,
            training_goal   TEXT,
            discipline_req  TEXT,
            main_courses    TEXT,
            postgrad_dir    TEXT,
            employment_dir  TEXT,
            hot_schools     TEXT[],
            image_path      TEXT,
            created_at      TIMESTAMPTZ DEFAULT now()
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mhp_code ON major_hot_profiles(code)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_mhp_name ON major_hot_profiles(name)")
    print("表 major_hot_profiles 已就绪")

    # ---- 入库 ----
    count = 0
    for r in results:
        # 查找 major_catalog 的 code
        cur.execute("SELECT code FROM major_catalog WHERE name=%s", (r["name"],))
        cat_row = cur.fetchone()
        code = cat_row[0] if cat_row else None

        cur.execute("SELECT id FROM major_hot_profiles WHERE name=%s", (r["name"],))
        exists = cur.fetchone()

        if exists:
            cur.execute(
                """UPDATE major_hot_profiles SET code=%s, seq=%s, degree=%s, length=%s,
                   gender_ratio=%s, introduction=%s, subject_req=%s, career=%s,
                   training_goal=%s, discipline_req=%s, main_courses=%s, postgrad_dir=%s,
                   employment_dir=%s, hot_schools=%s, image_path=%s WHERE name=%s""",
                (code, r["seq"], r["degree"], r["length"], r["gender_ratio"],
                 r["introduction"], r["subject_req"], r["career"],
                 r["training_goal"], r["discipline_req"], r["main_courses"],
                 r["postgrad_dir"], r["employment_dir"], r["hot_schools"],
                 r["image_path"], r["name"]),
            )
        else:
            cur.execute(
                """INSERT INTO major_hot_profiles
                   (code, name, seq, degree, length, gender_ratio, introduction,
                    subject_req, career, training_goal, discipline_req, main_courses,
                    postgrad_dir, employment_dir, hot_schools, image_path)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (code, r["name"], r["seq"], r["degree"], r["length"], r["gender_ratio"],
                 r["introduction"], r["subject_req"], r["career"],
                 r["training_goal"], r["discipline_req"], r["main_courses"],
                 r["postgrad_dir"], r["employment_dir"], r["hot_schools"],
                 r["image_path"]),
            )
        count += 1
    print(f"\n入库完成: {count} 条")

    # ---- 报告 ----
    cur.execute("SELECT count(*) FROM major_hot_profiles")
    total = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM major_hot_profiles WHERE code IS NOT NULL")
    with_code = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM major_hot_profiles WHERE introduction IS NOT NULL AND introduction != ''")
    with_intro = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM major_hot_profiles WHERE career IS NOT NULL OR employment_dir IS NOT NULL")
    with_career = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM major_hot_profiles WHERE array_length(hot_schools,1) > 0")
    with_schools = cur.fetchone()[0]

    print(f"\n=== 报告 ===")
    print(f"总记录: {total}")
    print(f"关联到 major_catalog: {with_code}")
    print(f"有专业介绍: {with_intro}")
    print(f"有就业方向: {with_career}")
    print(f"有热门院校: {with_schools}")

    cur.execute("SELECT name FROM major_hot_profiles WHERE code IS NULL ORDER BY seq")
    rows = cur.fetchall()
    if rows:
        print(f"\n未关联 major_catalog({len(rows)}条): {[r[0] for r in rows]}")

    conn.close()


if __name__ == "__main__":
    main()
