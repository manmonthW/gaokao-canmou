"""静态材料（院校图、PDF、分布图等）改由 Vercel Blob 托管时的读取层。

- 未设置 ASSET_MANIFEST（EWS 容器 / 本地开发）：USE_BLOB=False，各路由照旧读本地 2026allmaterial/。
- 设置 ASSET_MANIFEST：文件已由 webapp/scripts/blob/ 上传到 Blob，清单 JSON 为
  {key: {"url": ..., "size": ...}}；端点改为 302 跳转到 Blob 地址，存在性/大小也读清单。

key 统一为相对 2026allmaterial/ 的路径（正斜杠），例如 "热门大学介绍/985/东北大学.png"。
热门大学介绍的图片在上传前已按 hot_schools.crop_card 裁剪好。
"""
import json
import os
from functools import lru_cache

from fastapi import HTTPException
from fastapi.responses import RedirectResponse

ASSET_MANIFEST = os.environ.get("ASSET_MANIFEST", "").strip()
USE_BLOB = bool(ASSET_MANIFEST)
MATERIAL_DIRNAME = "2026allmaterial"
# Blob 文件按固定路径覆盖上传；跳转结果允许浏览器缓存 1 小时，更新素材后最多 1 小时生效
_REDIRECT_CACHE = "public, max-age=3600"


@lru_cache(maxsize=1)
def manifest() -> dict[str, dict]:
    path = ASSET_MANIFEST
    if not os.path.isabs(path):
        # 相对路径以 backend/ 为基准（Vercel 上 backend/ 即服务根目录）
        path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), path)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def size(key: str) -> int | None:
    entry = manifest().get(key)
    return entry["size"] if entry else None


def list_dir(prefix: str) -> list[str]:
    """prefix 目录下（不递归）的文件名。"""
    prefix = prefix.rstrip("/") + "/"
    return sorted(
        k[len(prefix):] for k in manifest()
        if k.startswith(prefix) and "/" not in k[len(prefix):]
    )


def key_from_material_path(path: str) -> str | None:
    """库里存的本地绝对路径（…/2026allmaterial/热门大学介绍/985/x.png）→ 清单 key。"""
    parts = path.replace("\\", "/").split("/")
    if MATERIAL_DIRNAME not in parts:
        return None
    rel = parts[len(parts) - parts[::-1].index(MATERIAL_DIRNAME):]
    if not rel or any(p in ("", ".", "..") for p in rel):
        return None
    return "/".join(rel)


def redirect(key: str, missing: str = "文件未找到"):
    entry = manifest().get(key)
    if not entry:
        raise HTTPException(404, missing)
    return RedirectResponse(entry["url"], status_code=302, headers={"Cache-Control": _REDIRECT_CACHE})
