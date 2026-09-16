"""证据账本单测：eid 自增、get/all、render 不崩、长列表截断生效。"""
from app.agent.evidence import EvidenceLedger, _MAX_LIST_ITEMS, _truncate


def test_add_returns_incrementing_eids():
    led = EvidenceLedger()
    e1 = led.add("locate_rank", {"rank": 1000}, {"ok": True})
    e2 = led.add("search_candidates", {"batch": "本科批"}, {"items": []})
    assert e1 == "E1"
    assert e2 == "E2"
    assert [e.eid for e in led.all()] == ["E1", "E2"]


def test_get_by_eid():
    led = EvidenceLedger()
    eid = led.add("get_major_info", {"name": "计算机科学与技术"}, {"code": "080901"})
    ev = led.get(eid)
    assert ev is not None
    assert ev.tool == "get_major_info"
    assert ev.data == {"code": "080901"}
    assert led.get("E999") is None


def test_render_empty():
    led = EvidenceLedger()
    assert led.render_for_prompt() == "（暂无证据）"


def test_render_contains_eid_and_tool():
    led = EvidenceLedger()
    led.add("locate_rank", {"rank": 1000}, {"score": 600})
    text = led.render_for_prompt()
    assert "[E1]" in text
    assert "locate_rank" in text
    assert "rank=1000" in text


def test_truncate_long_list():
    long = list(range(_MAX_LIST_ITEMS + 30))
    out = _truncate(long)
    # 截断到上限 + 1 条计数标记
    assert len(out) == _MAX_LIST_ITEMS + 1
    assert isinstance(out[-1], str)
    assert "已截断" in out[-1]


def test_truncate_nested_dict_list():
    payload = {"items": list(range(50)), "meta": {"tags": list(range(50))}}
    out = _truncate(payload)
    assert len(out["items"]) == _MAX_LIST_ITEMS + 1
    assert len(out["meta"]["tags"]) == _MAX_LIST_ITEMS + 1


def test_add_truncates_data():
    led = EvidenceLedger()
    eid = led.add("search_candidates", {}, {"items": list(range(100))})
    ev = led.get(eid)
    assert len(ev.data["items"]) == _MAX_LIST_ITEMS + 1
