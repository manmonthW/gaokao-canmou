from app.services.plan_analysis import analyze_plan


def entry(risk, rank, code="1", major="01", **extra):
    return {
        "risk": risk, "last_year_rank": rank, "school_code": code,
        "school_name": f"学校{code}", "major_code": major, "major_name": f"专业{major}",
        **extra,
    }


def test_empty_plan():
    result = analyze_plan({"entries": []})
    assert result["ok"] is False
    assert result["issues"] == 0


def test_healthy_plan():
    entries = [
        entry("冲", 9000, "1"), entry("稳", 11000, "2"),
        entry("稳", 13000, "3"), entry("保", 16000, "4"),
        entry("保", 18000, "5"), entry("保", 20000, "6"),
    ]
    result = analyze_plan({"strategy": "均衡", "entries": entries})
    assert result["ok"] is True
    assert result["counts"] == {"冲": 1, "稳": 2, "保": 3, "高波动": 0, "数据不足": 0}


def test_detects_duplicates_tail_and_order():
    entries = [
        entry("冲", 10000), entry("稳", 9000, "1"),
        entry("稳", 12000, "2"), entry("冲", 13000, "3"), entry("稳", 14000, "4"),
    ]
    result = analyze_plan({"entries": entries})
    text = "\n".join(result["warnings"])
    assert result["ok"] is False
    assert "重复" in text
    assert "尾部保底不足" in text
    assert "顺序倒退" in text


def test_trend_is_note_not_problem():
    entries = [
        entry("冲", 9000, "1"), entry("稳", 11000, "2", trend_label="持续升温"),
        entry("稳", 13000, "3"), entry("保", 16000, "4"),
        entry("保", 18000, "5"), entry("保", 20000, "6"),
    ]
    result = analyze_plan({"entries": entries})
    assert result["ok"] is True
    assert "门槛连升两年" in result["notes"][0]
