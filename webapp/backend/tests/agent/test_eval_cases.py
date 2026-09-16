import json
from collections import Counter
from pathlib import Path


def test_phase1_eval_cases_are_complete_and_well_formed():
    path = Path(__file__).parent / "eval" / "cases.yaml"
    suite = json.loads(path.read_text(encoding="utf-8"))
    cases = suite["cases"]

    assert suite["version"] == "phase1-v1"
    assert len(cases) == 55
    assert len({case["id"] for case in cases}) == len(cases)
    assert Counter(case["category"] for case in cases) == {
        "find_options": 30,
        "explain_unit": 15,
        "guard": 10,
    }
    for case in cases:
        assert case["question"].strip()
        assert isinstance(case["profile"], dict)
        assert isinstance(case["expected_tools"], list)
        if case["category"] == "guard":
            assert case["must_refuse"] is True
        else:
            assert case["expected_intent"] == case["category"]
