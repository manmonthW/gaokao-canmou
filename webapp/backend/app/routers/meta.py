import os

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.schemas import MetaResponse
from app.services import meta as svc

router = APIRouter(tags=["meta"])


@router.get("/meta", response_model=MetaResponse)
async def meta():
    """下拉筛选枚举。"""
    return await svc.get_meta()


# ---------- 选科组合专业覆盖率（3+1+2，12 种组合） ----------
# 数据源：2026allmaterial/新高考选科指南深度分析科目组合及专业选择/，
# 覆盖率编码在原图文件名中（如「02 物理-化学-生物737」= 73.7%）。
# 口径：全国通用参考值（第三方整理），非辽宁省专属。
_COMBO_DIR = "新高考选科指南深度分析科目组合及专业选择"
_COMBOS = [
    # (id, 首选, 再选(排序后), 覆盖率%, 分析图文件名)
    ("wl-hx-zz", "物理", ["化学", "政治"], 76.9, "01 物理-化学-政治769.jpg"),
    ("wl-hx-sw", "物理", ["化学", "生物"], 73.7, "02 物理-化学-生物737.jpg"),
    ("wl-hx-dl", "物理", ["化学", "地理"], 73.6, "03 物理-化学-地理736.jpg"),
    ("wl-zz-sw", "物理", ["政治", "生物"], 39.4, "04 物理-政治-生物394.jpg"),
    ("wl-zz-dl", "物理", ["政治", "地理"], 37.2, "05 物理-政治-地理372.jpg"),
    ("wl-sw-dl", "物理", ["生物", "地理"], 36.1, "06 物理-生物-地理361.jpg"),
    ("ls-sw-zz", "历史", ["生物", "政治"], 35.5, "07 历史-生物-政治355.jpg"),
    ("ls-hx-zz", "历史", ["化学", "政治"], 35.4, "08 历史-化学-政治354.jpg"),
    ("ls-dl-zz", "历史", ["地理", "政治"], 35.0, "09 历史-地理-政治350.jpg"),
    ("ls-hx-sw", "历史", ["化学", "生物"], 32.3, "10 历史-化学-生物323.jpg"),
    ("ls-sw-dl", "历史", ["生物", "地理"], 32.2, "11 历史-生物-地理322.jpg"),
    ("ls-hx-dl", "历史", ["化学", "地理"], 32.1, "12 历史-化学-地理321.jpg"),
]
_OVERVIEW_IMG = "12种选科组合专业覆盖率总览.png"

_MAT_ROOT = os.environ.get(
    "GUIDE_PDF_ROOT",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__)))))),
        "2026allmaterial",
    ),
)


@router.get("/meta/subject-combos")
async def subject_combos():
    """12 种 3+1+2 选科组合的专业覆盖率与组合分析图。"""
    items = []
    for cid, first, electives, cov, img in _COMBOS:
        path = os.path.join(_MAT_ROOT, _COMBO_DIR, img)
        items.append({
            "id": cid, "first": first, "electives": electives,
            "coverage": cov, "image": img, "available": os.path.exists(path),
        })
    overview_path = os.path.join(_MAT_ROOT, _COMBO_DIR, _OVERVIEW_IMG)
    return {
        "items": items,
        "overview_image": _OVERVIEW_IMG,
        "overview_available": os.path.exists(overview_path),
        "note": ("覆盖率为全国通用参考值（第三方整理），非辽宁省专属口径；"
                 "实际可报范围以本站 2027 官方选科要求核验为准。"),
    }


@router.get("/meta/subject-combos/{cid}/image")
async def subject_combo_image(cid: str):
    """按 id 白名单返回组合分析图（overview 为总览图）。"""
    filename = None
    if cid == "overview":
        filename = _OVERVIEW_IMG
    else:
        for c, _f, _e, _cov, img in _COMBOS:
            if c == cid:
                filename = img
                break
    if filename is None:
        raise HTTPException(404, f"未知组合 id：{cid}")
    path = os.path.join(_MAT_ROOT, _COMBO_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(404, "该图片尚未放入材料目录")
    media = "image/png" if filename.lower().endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media, filename=filename)
