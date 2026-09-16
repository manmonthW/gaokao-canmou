"""工具层单测：不走真实模型、不碰真实数据库。

monkeypatch 替换工具包引用的 service 函数（同 test_locate 风格），逐个验证：
  1. 入参校验：非法入参 raise（Pydantic）
  2. 服务调用参映射正确（透传给已确认签名）
  3. 裁剪生效（长列表被 EvidenceLedger 截断）
  4. 证据账本写入（eid 可溯）
"""
import asyncio

import pytest
from pydantic import ValidationError

from app.agent.evidence import EvidenceLedger, _MAX_LIST_ITEMS
from app.agent.tools import build_tools
from app import db
from app.services import locate, match, schools
from app.services import major_catalog


def _by_name(tools):
    return {t.name: t for t in tools}


def _run_tool(tool, **kwargs):
    """StructuredTool 包的是 async coroutine，用 ainvoke 跑。"""
    return asyncio.run(tool.ainvoke(kwargs))


# ----------------------------- 工具集合 -----------------------------

def test_build_tools_returns_seven():
    led = EvidenceLedger()
    tools = build_tools(led)
    names = set(_by_name(tools))
    assert names == {
        "locate_rank",
        "search_candidates",
        "get_unit_detail",
        "get_school_profile",
        "get_major_info",
        "check_subject_req",
        "rank_sensitivity",
    }


# ----------------------------- locate_rank -----------------------------

def test_locate_rank_maps_and_writes_evidence(monkeypatch):
    seen = {}

    async def fake_rank_context(category, subject, rank, batch=None):
        seen.update(category=category, subject=subject, rank=rank, batch=batch)
        return {"score": 600}

    monkeypatch.setattr(locate, "rank_context", fake_rank_context)
    led = EvidenceLedger()
    tool = _by_name(build_tools(led))["locate_rank"]

    out = _run_tool(tool, category="普通类", subject="物理", rank=1000, batch="本科批")
    assert seen == {"category": "普通类", "subject": "物理", "rank": 1000, "batch": "本科批"}
    assert out["eid"] == "E1"
    assert out["data"] == {"score": 600}
    # 证据账本可溯
    ev = led.get("E1")
    assert ev.tool == "locate_rank"
    assert ev.args["rank"] == 1000
    assert ev.data == {"score": 600}


def test_locate_rank_rejects_nonpositive_rank(monkeypatch):
    async def fake_rank_context(*a, **k):
        raise AssertionError("service 不应被调到")

    monkeypatch.setattr(locate, "rank_context", fake_rank_context)
    tool = _by_name(build_tools(EvidenceLedger()))["locate_rank"]
    with pytest.raises((ValidationError, ValueError)):
        _run_tool(tool, category="普通类", subject="物理", rank=0)


# ----------------------------- search_candidates -----------------------------

def test_search_candidates_maps_all_kwargs(monkeypatch):
    seen = {}

    async def fake_match(**kwargs):
        seen.update(kwargs)
        return {"items": [1, 2, 3]}

    monkeypatch.setattr(match, "match", fake_match)
    tool = _by_name(build_tools(EvidenceLedger()))["search_candidates"]

    out = _run_tool(
        tool,
        year=2025,
        category="普通类",
        subject="物理",
        batch="本科批",
        rank=1000,
        province="辽宁",
        level="985",
        major_keyword="计算机",
        risk="稳",
    )
    assert seen["year"] == 2025
    assert seen["batch"] == "本科批"
    assert seen["rank"] == 1000
    assert seen["province"] == "辽宁"
    assert seen["level"] == "985"
    assert seen["major_keyword"] == "计算机"
    assert seen["risk"] == "稳"
    # 默认分页
    assert seen["page"] == 1
    assert seen["page_size"] == 30
    assert out["eid"] == "E1"


def test_search_candidates_page_size_cap(monkeypatch):
    async def fake_match(**kwargs):
        return {}

    monkeypatch.setattr(match, "match", fake_match)
    tool = _by_name(build_tools(EvidenceLedger()))["search_candidates"]
    with pytest.raises((ValidationError, ValueError)):
        _run_tool(
            tool,
            year=2025,
            category="普通类",
            subject="物理",
            batch="本科批",
            page_size=500,  # > 100
        )


def test_search_candidates_truncates_long_list(monkeypatch):
    async def fake_match(**kwargs):
        return {"items": list(range(100))}

    monkeypatch.setattr(match, "match", fake_match)
    led = EvidenceLedger()
    tool = _by_name(build_tools(led))["search_candidates"]
    _run_tool(tool, year=2025, category="普通类", subject="物理", batch="本科批")
    ev = led.get("E1")
    assert len(ev.data["items"]) == _MAX_LIST_ITEMS + 1


# ----------------------------- get_unit_detail -----------------------------

def test_get_unit_detail_maps(monkeypatch):
    seen = {}

    async def fake_get_school_major(code, major_name, major_code=None, year=None, category=None):
        seen.update(
            code=code, major_name=major_name, major_code=major_code, year=year, category=category
        )
        return {"rows": []}

    monkeypatch.setattr(schools, "get_school_major", fake_get_school_major)
    tool = _by_name(build_tools(EvidenceLedger()))["get_unit_detail"]
    out = _run_tool(
        tool, code="10001", major_name="计算机科学与技术", year=2024, category="普通类"
    )
    assert seen["code"] == "10001"
    assert seen["major_name"] == "计算机科学与技术"
    assert seen["year"] == 2024
    assert out["eid"] == "E1"


# ----------------------------- get_school_profile -----------------------------

def test_get_school_profile_merges_base_and_strength(monkeypatch):
    async def fake_get_school(code):
        return {"name": "某大学", "code": code}

    async def fake_get_school_strength(code):
        return {"tags": ["一流学科"]}

    monkeypatch.setattr(schools, "get_school", fake_get_school)
    monkeypatch.setattr(schools, "get_school_strength", fake_get_school_strength)
    led = EvidenceLedger()
    tool = _by_name(build_tools(led))["get_school_profile"]
    out = _run_tool(tool, code="10001")
    assert out["data"]["school"]["name"] == "某大学"
    assert out["data"]["strength"]["tags"] == ["一流学科"]
    assert led.get("E1").tool == "get_school_profile"


# ----------------------------- get_major_info -----------------------------

def test_get_major_info_maps(monkeypatch):
    seen = {}

    async def fake_get_major_detail(name):
        seen["name"] = name
        return {"code": "080901"}

    monkeypatch.setattr(major_catalog, "get_major_detail", fake_get_major_detail)
    tool = _by_name(build_tools(EvidenceLedger()))["get_major_info"]
    out = _run_tool(tool, name="计算机科学与技术")
    assert seen["name"] == "计算机科学与技术"
    assert out["data"] == {"code": "080901"}


# ----------------------------- check_subject_req -----------------------------

def test_check_subject_req_inline_query_and_lookup(monkeypatch):
    fetched = {}

    async def fake_fetch_all(sql, params=None):
        fetched["sql"] = sql
        fetched["params"] = params
        return [("10001", "某大学", "计算机科学与技术", "物理", "化学")]

    def fake_build_req_indexes(rows):
        fetched["rows"] = rows
        return {"idx": True}

    def fake_lookup_reqs(idx, school, major):
        fetched["lookup"] = (school, major)
        return ([("物理", "化学")], "exact", True)

    monkeypatch.setattr(db, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(match, "build_req_indexes", fake_build_req_indexes)
    monkeypatch.setattr(match, "lookup_reqs", fake_lookup_reqs)

    led = EvidenceLedger()
    tool = _by_name(build_tools(led))["check_subject_req"]
    out = _run_tool(
        tool,
        year=2024,
        category="普通类",
        subject="物理",
        batch="本科批",
        school="某大学",
        major="计算机科学与技术",
    )
    # 内联查询仅依赖年份
    assert fetched["params"] == (2024,)
    assert "subject_requirements" in fetched["sql"]
    assert fetched["lookup"] == ("某大学", "计算机科学与技术")
    assert out["data"]["match_level"] == "exact"
    assert out["data"]["school_known"] is True
    assert led.get("E1").tool == "check_subject_req"


# ----------------------------- rank_sensitivity -----------------------------

def test_rank_sensitivity_maps(monkeypatch):
    seen = {}

    async def fake_sensitivity(**kwargs):
        seen.update(kwargs)
        return {"buckets": []}

    monkeypatch.setattr(match, "sensitivity", fake_sensitivity)
    tool = _by_name(build_tools(EvidenceLedger()))["rank_sensitivity"]
    out = _run_tool(
        tool, year=2025, category="普通类", subject="物理", batch="本科批", rank=1000
    )
    assert seen["year"] == 2025
    assert seen["rank"] == 1000
    assert out["eid"] == "E1"


# ----------------------------- profile 回退（不强制，工具显式入参为准） -----------------------------

def test_multiple_tools_share_incrementing_eids(monkeypatch):
    async def fake_rank_context(*a, **k):
        return {"score": 600}

    async def fake_get_major_detail(name):
        return {"code": "080901"}

    monkeypatch.setattr(locate, "rank_context", fake_rank_context)
    monkeypatch.setattr(major_catalog, "get_major_detail", fake_get_major_detail)
    led = EvidenceLedger()
    tools = _by_name(build_tools(led))
    o1 = _run_tool(tools["locate_rank"], category="普通类", subject="物理", rank=1000)
    o2 = _run_tool(tools["get_major_info"], name="计算机科学与技术")
    assert o1["eid"] == "E1"
    assert o2["eid"] == "E2"
    assert [e.eid for e in led.all()] == ["E1", "E2"]
