"""选科要求分层匹配单测（D2b 增强，audit_xk 审计定稿）。

覆盖 _xk_norm / _xk_base / _xk_enum_tokens / build_req_indexes / lookup_reqs：
L0 精确 → L1 归一 → L2 基础名（剥圆括号+方括号）→ L3 枚举反查 →
院校级行兜底 → 未收录拆分（major_missing / school_missing）+ 院校别名。
纯函数测试，不触达数据库。
"""
from app.services.match import (
    SCHOOL_ALIASES, _xk_base, _xk_enum_tokens, _xk_norm,
    build_req_indexes, lookup_reqs,
)

# 官方表样例行：(school_code, school_name, major_name, first_req, re_req)
REQ_ROWS = [
    ("10001", "太原理工大学", "化学", "物理", "化学"),
    ("10002", "石家庄铁道大学", "土木工程", "物理", "不限"),
    ("10003", "北京交通大学", "计算机类", "物理", "化学"),
    ("10003", "北京交通大学", "软件工程", "物理", "化学"),
    ("10004", "吉林化工学院", "化学工程与工艺", "物理", "化学"),
    ("10005", "云南师范大学", "数学与应用数学", "物理", "不限"),
    ("10006", "某大学", None, "不限", "不限"),  # 院校级空专业行
]
IDX = build_req_indexes(REQ_ROWS)


def test_norm_fullwidth_and_space():
    assert _xk_norm("　化学（试验班） ") == "化学(试验班)"
    assert _xk_norm("【计算机，软件】") == "[计算机,软件]"


def test_base_strips_paren_and_bracket():
    assert _xk_base("化学（试验班）") == "化学"
    assert _xk_base("化学（试验班）(拔尖人才培养班)") == "化学"
    assert _xk_base("计算机类[计算机科学与技术、软件工程]") == "计算机类"


def test_enum_tokens_skip_non_major_words():
    toks = _xk_enum_tokens("计算机类[计算机科学与技术、软件工程]")
    assert "计算机科学与技术" in toks and "软件工程" in toks
    # 试验班/专项/合作办学等不进枚举
    assert _xk_enum_tokens("化学(试验班)(教育部高校专项计划)") == []


def test_l0_exact():
    reqs, level, known = lookup_reqs(IDX, "太原理工大学", "化学")
    assert level == "exact" and known and reqs == [("物理", "化学")]


def test_l2_base_admission_suffix():
    """投档库带括号后缀 → 基础名命中（审计主力挽回层）。"""
    reqs, level, known = lookup_reqs(IDX, "太原理工大学", "化学(试验班)")
    assert level == "base" and known and reqs == [("物理", "化学")]
    reqs, level, _ = lookup_reqs(
        IDX, "太原理工大学", "化学（试验班）(拔尖人才培养班)")
    assert level == "base" and reqs == [("物理", "化学")]


def test_l3_enum_bracket():
    """北交大式大类枚举：招生名基础名不在表，方括号内专业反查命中。"""
    reqs, level, known = lookup_reqs(
        IDX, "北京交通大学", "信息科技英才班[计算机科学与技术、软件工程]")
    assert level == "enum" and known and reqs == [("物理", "化学")]


def test_school_alias():
    """更名院校别名：吉林化工大学 → 吉林化工学院。"""
    reqs, level, known = lookup_reqs(IDX, "吉林化工大学", "化学工程与工艺")
    assert level == "exact" and known and reqs == [("物理", "化学")]


def test_school_level_fallback():
    reqs, level, known = lookup_reqs(IDX, "某大学", "任意专业")
    assert level == "school" and known and reqs == [("不限", "不限")]


def test_major_missing_vs_school_missing():
    """学校在表但专业未收录 vs 学校完全不在表。"""
    reqs, level, known = lookup_reqs(IDX, "云南师范大学", "已停招专业")
    assert reqs is None and level is None and known is True
    reqs, level, known = lookup_reqs(IDX, "不存在的大学", "任意专业")
    assert reqs is None and level is None and known is False


def test_alias_targets_all_in_full_table():
    """别名表值必须真实存在于 2027 官方表（etl/verify_aliases.py 已验库，
    此处防回归：别名映射不能指向空字符串）。"""
    assert SCHOOL_ALIASES
    for src, dst in SCHOOL_ALIASES.items():
        assert src and dst and src != dst
