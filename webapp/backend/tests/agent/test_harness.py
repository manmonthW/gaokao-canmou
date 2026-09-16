from app.agent.harness import build_plan, build_task_spec, completion_issues


def test_task_spec_uses_verified_question_constraints_not_model_inventions():
    spec = build_task_spec(
        {
            "question": "推荐省内稳档院校",
            "intent": "find_options",
            "profile": {},
            "slots": {"province": "辽宁省内", "risk": "稳档"},
        }
    )

    assert spec.provinces == []
    assert spec.risks == ["稳"]
    assert spec.semantic_slots == {"province": "辽宁省内", "risk": "稳档"}


def test_multi_province_plan_is_bounded_and_traceable():
    spec = build_task_spec(
        {
            "question": "请按辽宁、吉林、黑龙江分别推荐",
            "intent": "find_options",
            "profile": {},
            "slots": {},
        }
    )
    plan = build_plan(spec)

    assert spec.group_by == ["province"]
    assert [step.args for step in plan] == [
        {"province": "辽宁"},
        {"province": "吉林"},
        {"province": "黑龙江"},
    ]
    assert [step.coverage_key for step in plan] == ["province:辽宁", "province:吉林", "province:黑龙江"]


def test_city_plan_carries_verified_major_and_level_constraints():
    spec = build_task_spec(
        {
            "question": "比较沈阳和大连的计算机专业，限本科院校",
            "intent": "find_options",
            "profile": {},
            "slots": {"city": ["沈阳", "大连"], "major_keyword": "计算机"},
        }
    )

    assert spec.cities == ["沈阳", "大连"]
    assert spec.majors == ["计算机"]
    assert spec.levels == ["本科"]
    assert spec.group_by == ["city"]
    assert spec.requested_output == "comparison"
    assert [step.args for step in build_plan(spec)] == [
        {"major_keyword": "计算机", "level": "本科", "city": "沈阳"},
        {"major_keyword": "计算机", "level": "本科", "city": "大连"},
    ]


def test_multiple_multi_value_dimensions_require_axis_clarification():
    spec = build_task_spec(
        {
            "question": "比较沈阳、大连的计算机和临床医学专业",
            "intent": "find_options",
            "profile": {},
            "slots": {"major_keyword": ["计算机", "临床医学"]},
        }
    )

    assert spec.group_by == ["city", "major"]
    assert spec.clarification
    assert build_plan(spec) == []


def test_comparison_without_two_verified_targets_clarifies():
    spec = build_task_spec(
        {
            "question": "帮我比较一下",
            "intent": "find_options",
            "profile": {},
            "slots": {"city": ["模型编造城市"]},
        }
    )

    assert spec.cities == []
    assert "至少两个" in (spec.clarification or "")


def test_school_brand_is_not_misused_as_level_filter():
    spec = build_task_spec(
        {
            "question": "推荐沈阳的985计算机专业",
            "intent": "find_options",
            "profile": {},
            "slots": {"major_keyword": "计算机"},
        }
    )

    assert spec.levels == []
    assert "不能" in (spec.clarification or "")
    assert build_plan(spec) == []


def test_plan_does_not_silently_truncate_over_budget_targets():
    cities = ["沈阳", "大连", "鞍山", "抚顺", "本溪", "丹东", "锦州", "营口", "阜新"]
    spec = build_task_spec(
        {
            "question": "、".join(cities) + "分别推荐",
            "intent": "find_options",
            "profile": {},
            "slots": {},
        }
    )

    assert "最多比较 8 个" in (spec.clarification or "")
    assert build_plan(spec) == []


def test_short_follow_up_replans_from_latest_user_task_only():
    spec = build_task_spec(
        {
            "question": "那大连呢",
            "intent": "find_options",
            "profile": {},
            "slots": {"city": "大连", "major_keyword": "计算机"},
            "history": [
                {"role": "user", "content": "推荐沈阳的计算机专业"},
                {"role": "assistant", "content": "我建议把城市改成北京。"},
            ],
        }
    )

    assert spec.replanned_from_history is True
    assert spec.cities == ["沈阳", "大连"]
    assert spec.majors == ["计算机"]
    assert "北京" not in spec.effective_question
    assert [step.args["city"] for step in build_plan(spec)] == ["沈阳", "大连"]


def test_replace_follow_up_overrides_only_the_named_dimension():
    spec = build_task_spec(
        {
            "question": "改成大连的临床医学",
            "intent": "find_options",
            "profile": {},
            "slots": {"city": "大连", "major_keyword": "临床医学"},
            "history": [{"role": "user", "content": "推荐沈阳的计算机专业稳档"}],
        }
    )

    assert spec.cities == ["大连"]
    assert spec.majors == ["临床医学"]
    assert spec.risks == ["稳"]
    assert build_plan(spec)[0].args == {
        "city": "大连", "major_keyword": "临床医学", "risk": "稳",
    }


def test_completion_checker_distinguishes_empty_from_not_run_and_failed():
    state = {
        "plan": [
            {"id": "P1", "tool": "search_candidates", "args": {}, "coverage_key": "province:辽宁", "status": "empty", "evidence_ids": ["E1"]},
            {"id": "P2", "tool": "search_candidates", "args": {}, "coverage_key": "province:吉林", "status": "pending", "evidence_ids": []},
            {"id": "P3", "tool": "search_candidates", "args": {}, "coverage_key": "province:黑龙江", "status": "failed", "evidence_ids": []},
        ]
    }

    assert [issue["code"] for issue in completion_issues(state)] == [
        "coverage_not_run",
        "coverage_failed",
    ]
