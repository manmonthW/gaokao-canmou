import os
import re
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app import assets

_MAP_DIR = "全国31省市本科高校分布图"
MAP_ROOT = os.environ.get(
    "PROVINCE_MAP_ROOT",
    "/home/ekewang/projects/gaokao/ln/2026allmaterial/全国31省市本科高校分布图",
)
_SUFFIX_RE = re.compile(r"省|市|壮族自治区|回族自治区|维吾尔自治区|自治区")

router = APIRouter(prefix="/province-maps", tags=["province-maps"])


def _normalize(name: str) -> str:
    return _SUFFIX_RE.sub("", name).strip()


def _index() -> dict[str, str]:
    out: dict[str, str] = {}
    if assets.USE_BLOB:
        filenames = assets.list_dir(_MAP_DIR)
    elif os.path.isdir(MAP_ROOT):
        filenames = os.listdir(MAP_ROOT)
    else:
        return out
    for filename in filenames:
        if not filename.endswith(".png") or "高校分布图" not in filename:
            continue
        province = filename.split("高校分布图", 1)[0]
        out[_normalize(province)] = filename
    return out


@router.get("")
async def province_maps():
    """返回有本科高校分布图的 31 个省级地区。"""
    return [{"province": key, "filename": value} for key, value in sorted(_index().items())]


@router.get("/{province}/image")
async def province_map_image(province: str):
    """按省级名称返回本科高校分布图；接受“辽宁”或“辽宁省”。"""
    filename = _index().get(_normalize(province))
    if not filename:
        raise HTTPException(status_code=404, detail="该省份分布图未找到")
    if assets.USE_BLOB:
        return assets.redirect(f"{_MAP_DIR}/{filename}", missing="该省份分布图未找到")
    path = os.path.join(MAP_ROOT, filename)
    return FileResponse(path, media_type="image/png", filename=filename)
