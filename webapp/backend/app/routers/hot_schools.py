"""热门大学介绍（每日一校卡片）只读 API。

数据来自 school_hot_profiles 表（由 etl/ocr_hot_schools.py 从
2026allmaterial/热门大学介绍/ 下的 PNG 卡片 OCR 入库）。

端点：
  GET /hot-schools/categories        分类列表 + 每类院校数
  GET /hot-schools?category=985      某分类下的院校卡片（默认全部）
  GET /hot-schools/{name}/image      卡片原图（PNG）
"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import FileResponse
from typing import Optional
import os
import re
from app import db

router = APIRouter(prefix="/hot-schools", tags=["hot-schools"])

# 「学校排名」区块在卡片中是一个三柱图：易度排名 / 校友会 / 软科，各带排名值与年份。
# OCR 后文字严重错乱（数字、标签、年份混排且夹杂噪声）。此处在读取层做「尽力而为」
# 的结构化解析，不改动库内原始 OCR 文本（无损、可回退）。解析不可靠时返回空，
# 前端隐藏文字块——卡片原图仍展示真实的排名柱状图。
_RANK_SOURCES = ["易度排名", "校友会", "软科"]
# 出现这些词说明该 ranking 字段其实混入了「院校简介」等正文，视为无有效排名
_RANK_JUNK_MARKERS = ["创办", "简称", "前身", "创立", "建校", "学位委员会", "研究生院",
                       "一级学科", "硕士点", "博士点"]


def parse_ranking(raw):
    """把错乱的 ranking OCR 文本解析成 [{source, rank, year}]。

    规则（保守）：
      - 若文本不含任何排名来源标签（易度排名/校友会/软科），或混入正文标志词 → 返回 []；
      - 否则按固定顺序取出「出现过的来源」，用标签前的前导小整数(1~3 位)作为排名候选，
        用文本中的 20xx 作为年份候选，按位置配对；数量不匹配时尽量配对，缺失留空。
    """
    if not raw or not isinstance(raw, str):
        return []
    text = raw.strip()
    if not text:
        return []
    # 含正文标志词 → 该字段是脏数据（简介误入），不展示排名
    if any(m in text for m in _RANK_JUNK_MARKERS):
        return []
    # 出现过的来源（按固定顺序）
    present = [s for s in _RANK_SOURCES if s in text]
    if not present:
        return []
    # 第一个来源标签出现的位置
    first_label_pos = min(text.find(s) for s in present if text.find(s) >= 0)
    head = text[:first_label_pos]
    tail = text[first_label_pos:]
    # 前导区的小整数（1~3 位，非 20xx）作为排名候选；排名合理区间 1~300
    ranks = []
    for n in re.findall(r"\d{1,3}", head):
        if re.fullmatch(r"20\d\d", n):
            continue
        v = int(n)
        if 1 <= v <= 300:
            ranks.append(v)
    # 标签区之后的 20xx 作为年份候选；合理区间 2018~2026
    years = [y for y in re.findall(r"20\d\d", tail) if 2018 <= int(y) <= 2026]
    items = []
    for i, src in enumerate(present):
        items.append({
            "source": src,
            "rank": ranks[i] if i < len(ranks) else None,
            "year": years[i] if i < len(years) else None,
        })
    # 若一个排名值都没解析出来，视为不可靠，返回空
    if all(it["rank"] is None for it in items):
        return []
    return items


# 图片根目录（与 OCR 入库脚本一致），用于图片端点路径白名单
# __file__ = .../webapp/backend/app/routers/hot_schools.py
# 项目根 = .../gaokao/ln （从 backend 向上两级）
_IMAGE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))),
    "2026allmaterial", "热门大学介绍",
)

# 卡片信息字段（不含 image_path 原文，单独走 image 端点）
_CARD_COLS = (
    "code, name, categories, established, location, nature, school_type, "
    "upgrade_rate, grad_recommend_rate, master_points, doctor_points, "
    "ranking, intro, discipline_eval, features, honors, faculty, image_path"
)


@router.get("/categories")
async def categories():
    """返回分类列表及各分类院校数（按 categories 数组展开统计）。"""
    rows = await db.fetch_all(
        "SELECT categories FROM school_hot_profiles WHERE categories IS NOT NULL"
    )
    counts: dict[str, int] = {}
    for (cats,) in rows:
        for c in cats:
            counts[c] = counts.get(c, 0) + 1
    # 固定顺序
    order = ["985", "211", "双一流", "C9", "E9", "五院四系", "两电一邮", "国防七子", "八大美院"]
    items = [{"category": c, "count": counts[c]} for c in order if c in counts]
    items += [{"category": c, "count": n} for c, n in counts.items() if c not in order]
    return {"categories": items, "total": sum(counts.values())}


@router.get("")
async def list_schools(category: Optional[str] = Query(None, description="按分类过滤，如 985/211/双一流")):
    """返回院校卡片。category 为空则返回全部。"""
    if category:
        rows = await db.fetch_all(
            f"SELECT {_CARD_COLS} FROM school_hot_profiles WHERE %s = ANY(categories) ORDER BY name",
            (category,),
        )
    else:
        rows = await db.fetch_all(
            f"SELECT {_CARD_COLS} FROM school_hot_profiles ORDER BY name"
        )
    out = []
    for r in rows:
        d = dict(zip(
            ["code", "name", "categories", "established", "location", "nature", "school_type",
             "upgrade_rate", "grad_recommend_rate", "master_points", "doctor_points",
             "ranking", "intro", "discipline_eval", "features", "honors", "faculty", "image_path"],
            r,
        ))
        d["has_image"] = bool(d.pop("image_path"))
        d["ranking_items"] = parse_ranking(d.get("ranking"))
        out.append(d)
    return {"schools": out, "count": len(out)}


@router.get("/{name}/image")
async def school_image(name: str):
    """返回院校卡片原图（PNG）。裁掉顶部『嗨写志愿/每日一校』与底部二维码后返回。"""
    from PIL import Image
    import io

    rows = await db.fetch_all(
        "SELECT image_path FROM school_hot_profiles WHERE name = %s",
        (name,),
    )
    if not rows or not rows[0][0]:
        raise HTTPException(status_code=404, detail="图片不存在")
    candidate = rows[0][0]
    abs_candidate = os.path.abspath(candidate)
    # 白名单：必须位于图片根目录内
    if not abs_candidate.startswith(os.path.abspath(_IMAGE_ROOT)):
        raise HTTPException(status_code=400, detail="非法路径")

    # 裁剪：顶部去掉『嗨写志愿 + 每日一校』标题区，底部去掉二维码（含上方扫码文字）
    CROP_TOP = 140
    CROP_BOTTOM = 200
    try:
        im = Image.open(abs_candidate).convert("RGB")
        w, h = im.size
        top = min(CROP_TOP, h // 3)
        bottom = max(0, h - min(CROP_BOTTOM, h // 3))
        im = im.crop((0, top, w, bottom))
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        buf.seek(0)
        return _png_response(buf.getvalue())
    except Exception:
        # 裁剪失败则退回原图
        return FileResponse(abs_candidate, media_type="image/png")


def _png_response(data: bytes):
    from fastapi.responses import Response
    return Response(content=data, media_type="image/png")
