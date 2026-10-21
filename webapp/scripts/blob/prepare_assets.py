"""准备上传到 Vercel Blob 的静态材料，输出到 staging 目录（保持相对 2026allmaterial/ 的路径）。

- 热门大学介绍/**.png：按 hot_schools.crop_card 裁剪后写入（与 EWS 返回的图一致）
- 其余文件：只收录后端实际会引用的，原样硬链接/复制

用法（在 webapp/backend 下）：
    .venv/bin/python ../scripts/blob/prepare_assets.py <2026allmaterial 路径> <staging 目录>
"""
import os
import shutil
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "backend"))
os.environ.setdefault("GAOKAO_DSN", "postgresql://unused@localhost/unused")  # 仅为满足 config import

from app.routers import guides, meta  # noqa: E402
from app.routers.hot_schools import crop_card  # noqa: E402
from app.routers.major_catalog import _HOT_DIR  # noqa: E402
from app.routers.province_maps import _MAP_DIR  # noqa: E402


def wanted(src_root: str) -> list[tuple[str, bool]]:
    """(相对路径, 是否需要裁剪)"""
    out: list[tuple[str, bool]] = []
    for g in guides._GROUPS:
        for it in g["items"]:
            out.append((it["filename"], False))
    for *_rest, img in meta._COMBOS:
        out.append((f"{meta._COMBO_DIR}/{img}", False))
    out.append((f"{meta._COMBO_DIR}/{meta._OVERVIEW_IMG}", False))
    for d in (_MAP_DIR, _HOT_DIR):
        for f in sorted(os.listdir(os.path.join(src_root, d))):
            if f.endswith(".png"):
                out.append((f"{d}/{f}", False))
    hot = os.path.join(src_root, "热门大学介绍")
    for dirpath, _dirs, files in os.walk(hot):
        for f in sorted(files):
            if f.endswith(".png"):
                rel = os.path.relpath(os.path.join(dirpath, f), src_root)
                out.append((rel.replace(os.sep, "/"), True))
    return out


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src_root, dst_root = map(os.path.abspath, sys.argv[1:])
    missing, total = [], 0
    for rel, crop in wanted(src_root):
        src = os.path.join(src_root, rel)
        dst = os.path.join(dst_root, rel)
        if not os.path.isfile(src):
            missing.append(rel)
            continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if crop:
            try:
                data = crop_card(src)
            except Exception as exc:  # noqa: BLE001 - 与线上一致：裁剪失败退回原图
                print(f"裁剪失败，使用原图：{rel}（{exc}）")
                shutil.copyfile(src, dst)
            else:
                with open(dst, "wb") as f:
                    f.write(data)
        else:
            shutil.copyfile(src, dst)
        total += os.path.getsize(dst)
    count = sum(len(files) for _d, _s, files in os.walk(dst_root))
    print(f"已准备 {count} 个文件，共 {total / 1024 / 1024:.1f} MB → {dst_root}")
    if missing:
        print(f"源目录缺少 {len(missing)} 个文件（后端会显示为不可用）：")
        for rel in missing:
            print("  ", rel)


if __name__ == "__main__":
    main()
