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
    assert [step.coverage_key for step in plan] == ["辽宁:all", "吉林:all", "黑龙江:all"]


def test_completion_checker_distinguishes_empty_from_not_run_and_failed():
    state = {
        "plan": [
            {"id": "P1", "tool": "search_candidates", "args": {}, "coverage_key": "辽宁:all", "status": "empty", "evidence_ids": ["E1"]},
            {"id": "P2", "tool": "search_candidates", "args": {}, "coverage_key": "吉林:all", "status": "pending", "evidence_ids": []},
            {"id": "P3", "tool": "search_candidates", "args": {}, "coverage_key": "黑龙江:all", "status": "failed", "evidence_ids": []},
        ]
    }

    assert [issue["code"] for issue in completion_issues(state)] == [
        "coverage_not_run",
        "coverage_failed",
    ]
