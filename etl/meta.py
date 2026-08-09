import re, os


def infer_meta(text, filename):
    """从内容文本(标题/工作表名)推导 年份/类别/批次/学科类/是否征集。"""
    t = text or ""
    lower = filename.lower()
    m = re.search(r"20\d{2}", filename)
    year = int(m.group()) if m else None

    # 类别优先看标题行（前几行）：体育类表的数据行里可能出现
    # 「成都艺术职业大学」「体育艺术表演」等字样，全文扫描会把
    # 体育类误判为艺术类；标题不含类别词时再用全文兜底。
    head = " ".join(l for l in t.splitlines()[:6])
    cat_src = head if ("艺术" in head or "体育" in head) else t
    if "艺术" in cat_src:
        cat = "艺术类"
    elif "体育" in cat_src:
        cat = "体育类"
    else:
        cat = "普通类"
    if "物理" in t:
        subj = "物理学科类"
    elif "历史" in t:
        subj = "历史学科类"
    else:
        subj = None

    batch = None
    # 注意顺序：更具体的模式在前。
    # ①「专科提前批」系必须排在「本科提前批」之前：2024 高职（专科）
    #   提前批文件的 sheet 名被官方误写为「本科提前批次…」，正文才是
    #   「普通类高职（专科）提前批」；title_blob 含 sheet 名，若先匹配
    #   「本科提前批」会整批误判。
    # ②「提前批」是各具体批次的子串，放最后作兜底。
    for pat in ["本科提前批A段", "本科提前批B段",
                "高职（专科）提前批", "专科提前批",
                "本科提前批", "专科批", "本科批", "提前批"]:
        if pat in t:
            batch = pat
            break
    # 正文优先于 sheet 名：两者冲突时以正文为准（sheet 名可能被官方误写）
    # 并归一化官方同义写法「高职（专科）提前批」→ 库内惯例「专科提前批」
    if "高职（专科）提前批" in t and batch in ("本科提前批", "提前批", "高职（专科）提前批"):
        batch = "专科提前批"
    # 官方标题「高职（专科）批」== 库内惯例「专科批」（2024/2025 专科批大表标题均如此）
    if "高职（专科）批" in t and batch is None:
        batch = "专科批"
    if batch is None:  # 文件名兜底
        bn = lower.split(".")[0]
        if "bk" in bn and ("tq" in bn or bn.endswith("a") or "a" in bn[-3:]):
            batch = "本科提前批"
        elif "bk" in bn:
            batch = "本科批"
        elif "zk" in bn:
            batch = "专科批"
        elif "tq" in bn:
            batch = "提前批"

    is_coll = ("征集" in t) or ("zj" in lower)
    return dict(year=year, category=cat, subject=subj,
                batch=batch, is_collection=is_coll)


def title_blob(rows, sheet_name=""):
    """取表格前若干行 + 工作表名，作为元数据推导依据。"""
    head = []
    for r in rows[:6]:
        cells = [str(c) for c in r if c is not None and str(c).strip()]
        if cells:
            head.append(" ".join(cells))
    blob = " ".join(head)
    if sheet_name:
        blob = sheet_name + " " + blob
    return blob
