"""智能匹配类别边界：艺术类/体育类不做冲稳保分档（PRODUCT.md：普通类算法不直接套用）。

拦截发生在任何数据库访问之前——这里把 db 访问替换成直接失败，确认三个入口都不查库。
"""
import asyncio

import pytest

from app.services import match as m


@pytest.fixture(autouse=True)
def no_db(monkeypatch):
    async def boom(*a, **k):
        raise AssertionError("非普通类不应访问数据库")
    monkeypatch.setattr(m.db, "fetch_all", boom)
    monkeypatch.setattr(m.db, "fetch_one", boom)


BASE = dict(year=2027, subject="物理学科类", batch="本科批")


@pytest.mark.parametrize("category", ["艺术类", "体育类"])
def test_match_blocks_non_general(category):
    r = asyncio.run(m.match(category=category, rank=3000, **BASE))
    assert r["error_code"] == "category_unsupported"
    assert f"{category}暂不支持智能匹配" in r["error"]
    assert r["examinee"]["category"] == category
    assert "items" not in r and "totals" not in r


@pytest.mark.parametrize("category", ["艺术类", "体育类"])
def test_sensitivity_and_refresh_block_non_general(category):
    s = asyncio.run(m.sensitivity(category=category, rank=3000, **BASE))
    assert s["error_code"] == "category_unsupported"
    f = asyncio.run(m.refresh_snapshots(category=category, rank=3000, items=[], **BASE))
    assert f["error_code"] == "category_unsupported"


def test_general_category_not_blocked():
    assert m._category_unsupported("普通类") is None
