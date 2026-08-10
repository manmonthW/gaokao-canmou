import re


def _to_float(v):
    if v is None:
        return None
    s = str(v).strip()
    if s in ("", "-", "—", "—", "无", "None"):
        return None
    s = s.replace(",", "").replace("，", "")
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group()) if m else None


def _cell(row, idx):
    if idx is None or idx >= len(row):
        return None
    v = row[idx]
    return v if v is not None else None


def _map_cols(header):
    cols = {}
    for i, c in enumerate(header):
        s = str(c) if c is not None else ""
        if "院校" in s and ("编号" in s or "代码" in s):
            cols["school_code"] = i
        elif "院校" in s and ("名称" in s or "招生院校" in s):
            cols["school_name"] = i
        elif "专业" in s and ("编号" in s or "代号" in s or "代码" in s):
            cols["major_code"] = i
        elif "专业" in s and ("名称" in s or "招生专业" in s) and "备注" not in s:
            cols["major_name"] = i
        elif ("最低分" in s and "排序" not in s and "相同" not in s
              and "文化" not in s and "课总" not in s):
            cols["lowest"] = i
    return cols


def _tiebreak_cols(rows, header_idx, lowest):
    """在表头后找含 （一）..（七） 的子表头行，定位 7 个同分排序项列。"""
    for r in rows[header_idx: header_idx + 3]:
        cells = [str(c) if c is not None else "" for c in r]
        if any("（一）" in c or "(一)" in c for c in cells):
            idxs = [i for i, c in enumerate(cells)
                    if re.search(r"[（(]\s*[一二三四五六七八]", c)]
            if len(idxs) >= 7:
                return idxs[:7]
            break
    # 兜底：最低分后的连续 7 列
    if lowest is not None:
        return list(range(lowest + 1, lowest + 8))
    return []


def _extract_scores(cell):
    """从最低分单元格提取得分列表 [(label, value)]。

    - 数值 / 纯数字字符串        -> [(None, float)]
    - '综合评价成绩623.775'      -> [(None, 623.775)]
    - '甲类755.33\\n乙类778.00'   -> [('甲', 755.33), ('乙', 778.00)]
    - '综合评价合格\\n高考成绩642' -> [(None, 642)]   （仅一段含数字）
    - 说明性无数字文本（如“全部投档”）-> []  （调用方保留空分行）
    """
    if cell is None:
        return []
    if isinstance(cell, (int, float)):
        return [(None, float(cell))]
    s = str(cell).strip()
    if not s:
        return []
    nums = re.findall(r"-?\d+(?:\.\d+)?", s)
    if not nums:
        return []
    if len(nums) == 1:
        return [(None, float(nums[0]))]
    # 多值：按换行/分号分段，每段取首个数字，并尝试提取 甲/乙/一二… 标签
    out = []
    for p in re.split(r"[\n;；]+", s):
        m = re.search(r"-?\d+(?:\.\d+)?", p)
        if not m:
            continue
        label = None
        lm = re.search(r"[甲乙丙丁一二三四五六七八]", p)
        if lm:
            label = lm.group()
        out.append((label, float(m.group())))
    return out if out else [(None, float(n)) for n in nums]


def parse_sheet(rows):
    """把工作表解析为记录列表。返回 (records, header_found)。"""
    hdr = None
    for i, r in enumerate(rows):
        cells = [str(c) for c in r if c is not None]
        joined = " ".join(cells)
        # 表头行需同时含 院校+编号/代码+最低分/投档/录取，
        # 以排除仅含“投档最低分”的说明行
        if ("院校" in joined and ("编号" in joined or "代码" in joined)
                and ("最低分" in joined or "投档" in joined
                     or "录取" in joined)):
            hdr = i
            break
    if hdr is None:
        return [], False

    cols = _map_cols(rows[hdr])
    lowest = cols.get("lowest")
    tb = _tiebreak_cols(rows, hdr, lowest)

    # 数据起始行：跳过表头及可能的子表头行
    start = hdr + 1
    sub = rows[start] if start < len(rows) else []
    sub_cells = [str(c) if c not in (None, "") else "" for c in sub]
    if any("（一）" in c or "(一)" in c for c in sub_cells) or \
       (lowest is not None and all(str(c).strip() == "" for c in sub[:lowest + 1])):
        start += 1

    score_kind = "录取最低分" if "录取最低分" in " ".join(
        str(c) for c in rows[hdr]) else "投档最低分"

    records = []
    last_code = None
    for r in rows[start:]:
        sc = _cell(r, cols.get("school_code"))
        sn = _cell(r, cols.get("school_name"))
        if (sc is None or str(sc).strip() == "") and \
           (sn is None or str(sn).strip() == ""):
            continue  # 空行/合计行
        # 跳过说明行
        if sn is not None and ("注：" in str(sn) or "说明" in str(sn)):
            continue
        # 合并格前向填充：院校编号格为空但行有数据（如辽东学院定向就业行，
        # 编号沿用上方最近非空行），继承上方校码，避免 NULL 校码入库。
        if (sc is None or str(sc).strip() == "") and last_code is not None and \
           not any(k in str(sn) for k in ("合计", "总计")):
            sc = last_code
        if sc is not None and str(sc).strip():
            last_code = str(sc).strip()
        mc = _cell(r, cols.get("major_code"))
        mn = _cell(r, cols.get("major_name"))
        raw = _cell(r, lowest)
        base = {
            "school_code": str(sc).strip() if sc is not None else None,
            "school_name": str(sn).strip() if sn is not None else None,
            "major_code": (str(mc).strip() if mc is not None else None),
            "major_name": (str(mn).strip() if mn is not None else None),
            "score_kind": score_kind,
            "tb1": _to_float(_cell(r, tb[0] if len(tb) > 0 else None)),
            "tb2": _to_float(_cell(r, tb[1] if len(tb) > 1 else None)),
            "tb3": _to_float(_cell(r, tb[2] if len(tb) > 2 else None)),
            "tb4": _to_float(_cell(r, tb[3] if len(tb) > 3 else None)),
            "tb5": _to_float(_cell(r, tb[4] if len(tb) > 4 else None)),
            "tb6": _to_float(_cell(r, tb[5] if len(tb) > 5 else None)),
            "tb7": _to_float(_cell(r, tb[6] if len(tb) > 6 else None)),
            "raw_row": {k: (str(v) if v is not None else None)
                        for k, v in zip(
                            ["school_code", "school_name", "major_code",
                             "major_name", "lowest"] +
                            [f"tb{i}" for i in range(1, 8)],
                            [sc, sn, mc, mn, raw] +
                            [_cell(r, t) for t in tb])},
        }
        scores = _extract_scores(raw)
        if not scores:
            scores = [(None, None)]  # 无数字（如“全部投档”说明）：保留空分行
        for label, val in scores:
            rec = dict(base)
            rec["lowest_score"] = val
            if label is not None:
                rec["major_name"] = (rec.get("major_name") or "") + f"（{label}）"
            records.append(rec)
    return records, True


_NUM = re.compile(r"^\d+(?:\.\d+)?$")
# 院校编号：行首或「物理/历史学科类」前缀之后（征集表数据行），
# 允许 1-2 位字母前缀（P018/JV02/JX25/Q432 等）+ 2-6 位 ASCII 数字。
# 注意：lookaround 必须用 [0-9.] 而非 \d —— Python 的 \d 是 Unicode
# 数字类，「学科类」的「类」也是 \d，会把紧跟前缀的校码误排除。
_CODE = re.compile(r"(?<![0-9.])([A-Z]{0,2}[0-9]{2,6})(?![0-9.])")
# 提前批第一次投档行：编号 + 校名 + 单个总分（无同分排序项）
_TQ_LINE = re.compile(r"^([A-Z]{0,2}[0-9]{2,6})\s+([^0-9]+?)\s+([0-9]{3}(?:\.[0-9]+)?)\s*$")
# 提前批综合评价院校行：仅编号 + 校名，无投档线（与 2025 表格入库的
# NULL 分行为同一先例）
_TQ_NOSCORE = re.compile(r"^([A-Z]{0,2}[0-9]{2,6})\s+([^0-9]+?)\s*$")


def parse_pdf_text(pages, meta):
    """尽力从 OCR 文本抽取 (校码, 校名, 分数) 记录。"""
    records = []
    for page, text in pages:
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # 校码先定位：行首优先；否则行内搜（征集行以学科类开头）。
            # 校码本身是纯数字，必须先摘除再数数，否则会被计入
            # 数字序列，导致同分排序项整体错位。
            m = re.match(r"^([A-Z]{0,2}[0-9]{2,6})\b", line)
            if not m:
                m = _CODE.search(line)
            code = m.group(1) if m else None
            toks = re.split(r"[\s|/]+", line[m.end():] if m else line)
            nums = [t for t in toks if _NUM.match(t)]
            if len(nums) < 8:
                # 提前批第一次投档：仅「编号 + 校名 + 总分」，
                # 官方不提供同分排序项；综合评价院校无投档线记 NULL
                if meta.get("batch") and "提前批" in meta["batch"]:
                    mq = _TQ_LINE.match(line)
                    score = float(mq.group(3)) if mq else None
                    if not mq:
                        mq = _TQ_NOSCORE.match(line)
                    if mq:
                        records.append({
                            "school_code": mq.group(1),
                            "school_name": re.sub(r"[^\u4e00-\u9fffA-Za-z]",
                                                  "", mq.group(2)),
                            "major_code": None,
                            "major_name": None,
                            "score_kind": "投档最低分",
                            "lowest_score": score,
                            "tb1": None, "tb2": None, "tb3": None,
                            "tb4": None, "tb5": None, "tb6": None,
                            "tb7": None,
                            "raw_row": {"ocr_line": line},
                            "ocr_page": page,
                        })
                continue
            # 定位最后一个长度>=8 的连续数字段作为分数块
            runs, cur = [], []
            for t in toks:
                if _NUM.match(t):
                    cur.append(t)
                else:
                    if cur:
                        runs.append(cur); cur = []
            if cur:
                runs.append(cur)
            score_run = None
            for rn in reversed(runs):
                if len(rn) >= 8:
                    score_run = rn; break
            if not score_run:
                continue
            # 去掉末尾志愿号(<=9 的小数字)
            block = score_run[:]
            if len(block) >= 9 and float(block[-1]) <= 9:
                block = block[:-1]
            if len(block) < 8:
                continue
            lowest = float(block[0])
            tbs = [float(x) for x in block[1:8]]
            # 逐行学科类：征集表同一文件内混排两学科类，行首带前缀
            subject = None
            if line.startswith("历史学科类"):
                subject = "历史学科类"
            elif line.startswith("物理学科类"):
                subject = "物理学科类"
            # 校名/专业：校码之后、分数块之前的文字；若校码后紧跟
            # 专业代号（如 4Q/0X/D2），代号前为校名，代号后为专业名
            major_code = None
            major_name = None
            name = ""
            if code:
                rest = line[m.end():]
                sb = score_run[0]
                if sb in rest:
                    rest = rest[:rest.index(sb)]
                pm = re.search(r"\s([0-9A-Z]{2})\s", rest)
                if pm:
                    major_code = pm.group(1)
                    major_name = re.sub(r"\s+", "", rest[pm.end():]) or None
                    rest = rest[:pm.start()]
                name = re.sub(r"[^\u4e00-\u9fffA-Za-z]", "", rest)
            if not code or not name:
                continue
            records.append({
                "school_code": code,
                "school_name": name,
                "major_code": major_code,
                "major_name": major_name,
                "subject": subject,
                "score_kind": "投档最低分",
                "lowest_score": lowest,
                "tb1": tbs[0], "tb2": tbs[1], "tb3": tbs[2],
                "tb4": tbs[3], "tb5": tbs[4], "tb6": tbs[5], "tb7": tbs[6],
                "raw_row": {"ocr_line": line},
                "ocr_page": page,
            })
    return records
