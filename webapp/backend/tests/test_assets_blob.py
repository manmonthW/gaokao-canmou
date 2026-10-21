"""Blob 模式（ASSET_MANIFEST）下静态材料端点改为 302 跳转，存在性与大小读清单。"""
import asyncio
from urllib.parse import unquote

import pytest
from fastapi import HTTPException

from app import assets
from app.routers import guides, hot_schools, major_catalog, meta, province_maps

BASE = "https://blob.example/gaokao-assets/"
KEYS = {
    "辽宁省2026年普通高校招生志愿填报须知.pdf": 1234,
    "新高考选科指南深度分析科目组合及专业选择/01 物理-化学-政治769.jpg": 10,
    "全国31省市本科高校分布图/辽宁省高校分布图.png": 20,
    "热门专业盘点/clean/（11）自动化.png": 30,
    "热门大学介绍/985/东北大学.png": 40,
}


@pytest.fixture(autouse=True)
def blob_mode(monkeypatch):
    manifest = {k: {"url": BASE + k, "size": v} for k, v in KEYS.items()}
    monkeypatch.setattr(assets, "USE_BLOB", True)
    monkeypatch.setattr(assets, "manifest", lambda: manifest)


def _location(resp):
    assert resp.status_code == 302
    return unquote(resp.headers["location"])


def test_guides_metadata_and_redirect():
    out = asyncio.run(guides.guides())
    items = {it["id"]: it for g in out["groups"] for it in g["items"]}
    assert items["tianbao-xuzhi"]["available"] is True
    assert items["tianbao-xuzhi"]["size_bytes"] == 1234
    assert items["zhaosheng-jianzhang"]["available"] is False

    assert _location(asyncio.run(guides.guide_pdf("tianbao-xuzhi"))).endswith("填报须知.pdf")
    with pytest.raises(HTTPException) as exc:
        asyncio.run(guides.guide_pdf("zhaosheng-jianzhang"))
    assert exc.value.status_code == 404


def test_subject_combo_images():
    out = asyncio.run(meta.subject_combos())
    avail = {it["id"]: it["available"] for it in out["items"]}
    assert avail["wl-hx-zz"] is True and avail["wl-hx-sw"] is False
    assert out["overview_available"] is False
    assert "769.jpg" in _location(asyncio.run(meta.subject_combo_image("wl-hx-zz")))
    with pytest.raises(HTTPException):
        asyncio.run(meta.subject_combo_image("overview"))


def test_province_maps_list_and_image():
    assert asyncio.run(province_maps.province_maps()) == [
        {"province": "辽宁", "filename": "辽宁省高校分布图.png"}
    ]
    assert _location(asyncio.run(province_maps.province_map_image("辽宁省"))).endswith("辽宁省高校分布图.png")
    with pytest.raises(HTTPException):
        asyncio.run(province_maps.province_map_image("吉林"))


def test_major_hot_image():
    assert _location(asyncio.run(major_catalog.hot_image("自动化"))).endswith("自动化.png")
    with pytest.raises(HTTPException):
        asyncio.run(major_catalog.hot_image("临床医学"))


def test_hot_school_image_maps_db_path_to_key(monkeypatch):
    path = {"东北大学": "/home/x/2026allmaterial/热门大学介绍/985/东北大学.png",
            "坏路径": "/home/x/2026allmaterial/../etc/passwd",
            "越界": "/home/x/2026allmaterial/全国31省市本科高校分布图/辽宁省高校分布图.png"}

    async def fake_fetch_all(_sql, params):
        return [(path[params[0]],)]

    monkeypatch.setattr(hot_schools.db, "fetch_all", fake_fetch_all)
    assert _location(asyncio.run(hot_schools.school_image("东北大学"))).endswith("东北大学.png")
    for name in ("坏路径", "越界"):
        with pytest.raises(HTTPException) as exc:
            asyncio.run(hot_schools.school_image(name))
        assert exc.value.status_code == 400


def test_key_from_material_path():
    f = assets.key_from_material_path
    assert f("/a/2026allmaterial/热门大学介绍/985/x.png") == "热门大学介绍/985/x.png"
    assert f("C:\\a\\2026allmaterial\\热门大学介绍\\x.png") == "热门大学介绍/x.png"
    assert f("/a/other/x.png") is None
    assert f("/a/2026allmaterial/") is None
    assert f("/a/2026allmaterial/x/../y.png") is None
