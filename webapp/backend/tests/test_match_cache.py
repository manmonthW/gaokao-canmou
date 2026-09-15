"""匹配管线缓存单测（2026-09-15 重构）：单元集合缓存键与位次/筛选/再选科目无关、
同键冷启动单飞、数据版本变更失效、请求段不改共享单元，以及层次筛选不再被
选科查找的局部变量覆盖（旧实现 bug：层次筛选静默失效、艺术类恒为 0 条）。

纯内存测试：_build_units 与 get_data_version 以假实现替换，不触达数据库。
"""
import asyncio

import pytest

from app.services import match as m

CFG = m.MATCH_CONFIG


def _unit(code, level="本科", xk=None, best=10000, worst=14000, name="计算机科学与技术"):
    u = {
        "school_code": code, "school_name": f"学校{code}",
        "major_code": "01", "major_name": name, "catalog_name": None,
        "batch": "本科批", "province": "辽宁", "city": "沈阳", "level": level,
        "nature": "公办", "type": "理工", "is_985": False, "is_211": False,
        "is_dfc": False, "city_tier": "新一线", "strength_tags": [],
        "flags": [], "n_years": 2, "has_both_years": True,
        "best_rank": best, "worst_rank": worst, "median_rank": (best + worst) // 2,
        "last_year": 2026, "last_year_rank": worst, "last_year_score": 600,
        "span": worst - best, "continuous": True, "break_detected": False,
        "yearly": [(2025, best), (2026, worst)], "monotonic": None,
        "multi_unit_years": {}, "major_strength": [], "major_trend": None,
    }
    if xk is not None:
        u["_xk"] = xk
    return u


@pytest.fixture
def fake_units(monkeypatch):
    """替换建库与数据版本；返回 (构建调用计数, 可改的数据版本)。"""
    m._UNIT_CACHE.clear()
    m._UNIT_LOCKS.clear()
    calls = {"n": 0}
    state = {"version": "2026.3"}

    async def fake_build(**kw):
        calls["n"] += 1
        await asyncio.sleep(0.01)  # 让并发请求有机会排队
        return [_unit("A"), _unit("B", level="高职专科")], False

    async def fake_version():
        return state["version"]

    monkeypatch.setattr(m, "_build_units", fake_build)
    monkeypatch.setattr(m, "get_data_version", fake_version)
    yield calls, state
    m._UNIT_CACHE.clear()
    m._UNIT_LOCKS.clear()


def _prepare(**kw):
    base = dict(category="普通类", subject="物理学科类", batch="本科批", year=2027,
                rank=12000, cfg=CFG)
    base.update(kw)
    return m._prepare_candidates(**base)


def test_cache_key_ignores_rank_filters_and_electives(fake_units):
    """换位次、换筛选、填再选科目都命中同一份单元集合，不重复构建。"""
    calls, _ = fake_units

    async def run():
        await _prepare(rank=12000)
        await _prepare(rank=45678)
        await _prepare(rank=30000, province="辽宁", level="本科", electives=["化学"])
        await _prepare(rank=30000, exclude_flags=["中外合作"], has_both_years=True)
    asyncio.run(run())
    assert calls["n"] == 1


def test_cache_key_splits_by_batch_subject_and_version(fake_units):
    calls, state = fake_units

    async def run():
        await _prepare()
        await _prepare(batch="专科批")
        await _prepare(subject="历史学科类")
        state["version"] = "2027.1"  # 年度入库后 data_version 变化，旧键自然失效
        await _prepare()
    asyncio.run(run())
    assert calls["n"] == 4


def test_concurrent_cold_requests_build_once(fake_units):
    """高峰期同一批次的并发首请求只构建一次，且不遗留锁。"""
    calls, _ = fake_units

    async def run():
        await asyncio.gather(*[_prepare(rank=10000 + i) for i in range(8)])
    asyncio.run(run())
    assert calls["n"] == 1
    assert m._UNIT_LOCKS == {}


def test_level_filter_not_shadowed_by_subject_lookup():
    """回归：旧实现在选科查找循环里把局部变量命名为 level，覆盖了层次筛选参数。"""
    xk = ([("物理", "化学")], "exact", True, "化学", True)  # 选科匹配级别 = "exact"
    units = [_unit("A", xk=xk), _unit("B", level="高职专科", xk=xk)]
    kw = dict(rank=12000, subject="物理学科类", electives=None, subjreq_loaded=True,
              province=None, city=None, nature=None, type_=None, major_keyword=None,
              has_both_years=None, exclude_flags=None, cfg=CFG)
    filtered, cands, *_ = m._classify_units(units, level="本科", **kw)
    assert [c["school_code"] for c in filtered] == ["A"]
    # 未选层次时不应把任何单元筛掉（旧实现会拿 "exact" 当层次，筛成 0 条）
    filtered, cands, *_ = m._classify_units(units, level=None, **kw)
    assert len(filtered) == 2
    assert all(c["subject_match_level"] == "exact" for c in cands)


def test_classify_does_not_mutate_shared_units():
    """请求段返回的候选是新 dict；调用方排序/改键不影响缓存里的单元。"""
    units = [_unit("A"), _unit("B", best=20000, worst=26000)]
    snapshot = [dict(u) for u in units]
    kw = dict(subject="物理学科类", electives=None, subjreq_loaded=False,
              province=None, city=None, level=None, nature=None, type_=None,
              major_keyword=None, has_both_years=None, exclude_flags=None, cfg=CFG)
    filtered, cands, *_ = m._classify_units(units, rank=12000, **kw)
    filtered.sort(key=lambda c: c["school_code"], reverse=True)
    for c in cands:
        c["risk"] = "被调用方改掉"
    assert units == snapshot
    assert "_xk" not in cands[0]
    # 同一份单元在另一个位次下独立分档
    _, cands2, *_ = m._classify_units(units, rank=5000, **kw)
    assert cands2[0]["risk"] == "保"


def test_subject_exclusion_counts():
    """首选不符无条件排除；再选不符仅在填了再选时排除；未收录只警示不排除。"""
    first_bad = ([("历史", "不限")], "exact", True, "首选历史", False)
    re_needs_chem = ([("物理", "化学")], "exact", True, "化学", True)
    missing = (None, None, False, None, True)
    units = [_unit("A", xk=first_bad), _unit("B", xk=re_needs_chem), _unit("C", xk=missing)]
    kw = dict(rank=12000, subject="物理学科类", subjreq_loaded=True,
              province=None, city=None, level=None, nature=None, type_=None,
              major_keyword=None, has_both_years=None, exclude_flags=None, cfg=CFG)
    filtered, _, ex_first, ex_re, _ = m._classify_units(units, electives=["生物"], **kw)
    assert (ex_first, ex_re) == (1, 1)
    assert [c["school_code"] for c in filtered] == ["C"]
    assert filtered[0]["subject_status"] == "school_missing"
    assert "选科要求未收录" in filtered[0]["warning"]
    filtered, _, ex_first, ex_re, _ = m._classify_units(units, electives=None, **kw)
    assert (ex_first, ex_re) == (1, 0)
    assert [c["school_code"] for c in filtered] == ["B", "C"]
