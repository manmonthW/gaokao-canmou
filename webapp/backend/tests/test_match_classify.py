"""_classify / _normalize_batch 单测（A1 保档 margin + 区间文案，A4 批次别名归一）。

纯函数测试，不触达数据库。阈值基准来自 MATCH_CONFIG（safe_margin=0.85，
2025→2026 回测固化，见 webapp/scripts/backtest_report.txt）。
"""
from app.services.match import (
    MATCH_CONFIG, _classify, _normalize_batch, _build_unit_key, _batch_variants,
)


def _unit(best=10000, worst=14000, n_years=2, span=None, med=None, brk=False):
    med = med if med is not None else (best + worst) // 2
    return {
        "n_years": n_years, "best_rank": best, "worst_rank": worst,
        "median_rank": med, "span": span if span is not None else worst - best,
        "break_detected": brk,
    }


CFG = MATCH_CONFIG


def test_safe_margin_boundary():
    """A1：保档边界 = best × safe_margin，恰在线上判保、越线降稳。"""
    best = 10000
    safe_line = int(best * CFG["safe_margin"])  # 8500
    assert _classify(_unit(best=best), safe_line, CFG)[0] == "保"
    assert _classify(_unit(best=best), safe_line + 1, CFG)[0] == "稳"


def test_between_best_and_safe_line_is_stable():
    """A1：优于最难年门槛但未越过安全边际线 → 稳（原为保，乐观偏差修复）。"""
    best = 10000
    safe_line = int(best * CFG["safe_margin"])
    risk, reason = _classify(_unit(best=best), safe_line + (best - safe_line) // 2, CFG)
    assert risk == "稳"
    assert "安全边际线" in reason


def test_interval_wording():
    """A1：解释文案为区间语言（历史门槛区间 + 明年移动预期）。"""
    risk, reason = _classify(_unit(), 12000, CFG)
    assert risk in ("稳", "冲")
    assert "历史门槛区间" in reason


def test_high_volatility_priority():
    """高波动优先于保/稳/冲（相对波动≥0.5 且跨度≥2000）。"""
    u = _unit(best=5000, worst=10000, med=7500, span=5000)
    assert _classify(u, 1000, CFG)[0] == "高波动"
    # 单年数据不判高波动
    u1 = _unit(best=5000, worst=5000, med=5000, span=0, n_years=1)
    assert _classify(u1, 1000, CFG)[0] == "保"


def test_no_rank_is_insufficient():
    u = {"n_years": 0, "best_rank": None, "worst_rank": None,
         "median_rank": None, "span": None, "break_detected": False}
    assert _classify(u, 1000, CFG)[0] == "数据不足"


def test_break_and_single_year_notes():
    risk, reason = _classify(_unit(brk=True), 1000, CFG)
    assert "断档" in reason
    risk, reason = _classify(_unit(n_years=1, worst=10000), 1000, CFG)
    assert "仅 1 年" in reason


def test_batch_alias_normalization():
    """A4：本科提前批 A/B 段与 2025 本科提前批归一为同一单元键。"""
    assert _normalize_batch("本科提前批A段") == "本科提前批"
    assert _normalize_batch("本科提前批B段") == "本科提前批"
    assert _normalize_batch("本科批") == "本科批"
    k25 = _build_unit_key("0001", "01", "计算机科学与技术", "本科提前批")
    k26a = _build_unit_key("0001", "01", "计算机科学与技术", "本科提前批A段")
    k26b = _build_unit_key("0001", "01", "计算机科学与技术", "本科提前批B段")
    assert k25 == k26a == k26b
    # 不同专业仍分开
    assert _build_unit_key("0001", "02", "软件工程", "本科提前批A段") != k26a


def test_batch_variants_for_db_filter():
    """A4：请求本科提前批时 DB 过滤需展开含 A/B 段；普通批不展开。"""
    v = _batch_variants("本科提前批")
    assert set(v) == {"本科提前批", "本科提前批A段", "本科提前批B段"}
    assert _batch_variants("本科批") == ["本科批"]
    # 从别名段请求也能拿到全集
    assert set(_batch_variants("本科提前批A段")) == set(v)
