import re, os


def infer_meta(text, filename):
    """从内容文本(标题/工作表名)推导 年份/类别/批次/学科类/是否征集。"""
    t = text or ""
    lower = filename.lower()
    m = re.search(r"20\d{2}", filename)
    year = int(m.group()) if m else None

    if "艺术" in t:
        cat = "艺术类"
    elif "体育" in t:
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
    for pat in ["本科提前批A段", "本科提前批B段", "本科提前批",
                "专科批", "本科批", "提前批"]:
        if pat in t:
            batch = pat
            break
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
