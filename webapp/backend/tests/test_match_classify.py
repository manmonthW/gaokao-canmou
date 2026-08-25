"""_classify / _normalize_batch 单测（A1 保档 margin + 区间文案，A4 批次别名归一，
A5 稳/冲分界改锚最近一年 + 单调序列不判高波动 + 单元键改用规范化专业名）。

纯函数测试，不触达数据库。阈值基准来自 MATCH_CONFIG（safe_margin=0.85，
2024→2025 与 2025→2026 两对回测固化，见 webapp/scripts/backtest_report.txt）。
"""
from app.services.match import (
    MATCH_CONFIG, _classify, _normalize_batch, _build_unit_key, _batch_variants,
    _name_key, _risk_at,
)


def _unit(best=10000, worst=14000, n_years=2, span=None, med=None, brk=False,
          last=None, monotonic=None):
    med = med if med is not None else (best + worst) // 2
    return {
        "n_years": n_years, "best_rank": best, "worst_rank": worst,
        "median_rank": med, "span": span if span is not None else worst - best,
        "break_detected": brk,
        # A5：稳/冲分界锚在最近一年；缺省回退中位（等价于改动前的行为）
        "last_year_rank": last if last is not None else med,
        "monotonic": monotonic,
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
    """高波动优先于保/稳/冲（相对波动≥0.5 且跨度≥2000，且序列非单调）。"""
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


def test_monotonic_series_is_not_volatile():
    """A5：三年单向移动是趋势不是波动——跨度再大也不进「高波动」档。

    真实例：中国医科大学临床医学 9855→12013→16342，相对波动 54%、跨度 6487，
    旧规则会判「高波动」，但它是教科书式的连续趋势，应照常分档并由趋势说明解释。
    """
    seq = _unit(best=9855, worst=16342, med=12013, n_years=3,
                last=16342, monotonic="松")
    assert _classify(seq, 20000, CFG)[0] == "冲"
    # 同样的数字，若非单调（大小年），仍应判高波动
    osc = _unit(best=9855, worst=16342, med=12013, n_years=3,
                last=12013, monotonic=None)
    assert _classify(osc, 20000, CFG)[0] == "高波动"


def test_stable_reach_boundary_uses_last_year():
    """A5：稳/冲分界锚在最近一年门槛，而不是三年区间中位。"""
    # 中位 12000、最近年 14000：位次 13000 在旧口径判「冲」，新口径判「稳」
    # （跨度 4000/中位 12000 = 33% < 50%，不触发高波动）
    u = _unit(best=11000, worst=15000, med=12000, last=14000, n_years=3)
    risk, reason = _classify(u, 13000, CFG)
    assert risk == "稳"
    assert "最近年门槛 14000" in reason
    # 越过最近年门槛才转「冲」
    assert _classify(u, 14001, CFG)[0] == "冲"


def test_risk_at_projects_every_key_classify_reads():
    """_risk_at 的投影必须覆盖 _classify 读到的全部键。

    漏掉 last_year_rank / monotonic 会让新分界与高波动判定在敏感度试算、
    区间模式两条路径上静默退化——这类回归不报错，只会悄悄给错结果。
    """
    cand = {"n_years": 3, "best_rank": 11000, "worst_rank": 15000,
            "median_rank": 12000, "span": 4000, "break_detected": False,
            "last_year_rank": 14000, "monotonic": None}
    assert _risk_at(cand, 13000, CFG) == _classify(dict(cand), 13000, CFG)
    # 单调单元在两条路径下也必须同档（monotonic 若没投影过去就会分叉）
    mono = dict(cand, best_rank=9855, worst_rank=16342, median_rank=12013,
                span=6487, last_year_rank=16342, monotonic="松")
    assert _risk_at(mono, 20000, CFG)[0] == _classify(dict(mono), 20000, CFG)[0] == "冲"


def test_unit_key_uses_name_not_rotating_major_code():
    """省内专业代码逐年重排，不能做跨年身份；规范化专业名才是。

    中国医科大学「临床医学」2024 年代码 09、2025 年代码 04——按代码归并会把
    2024 年代码 04 的另一个专业接进同一条时间线。
    """
    y2024 = _build_unit_key("10159", "09", "临床医学", "本科批")
    y2025 = _build_unit_key("10159", "04", "临床医学", "本科批")
    assert y2024 == y2025
    other = _build_unit_key("10159", "04", "护理学", "本科批")
    assert other != y2025


def test_name_key_normalizes_fullwidth_punctuation():
    """同一单元跨年会混用全/半角逗号，规范化后必须相等。"""
    assert (_name_key("临床医学(5+3一体化，儿科学)")
            == _name_key("临床医学(5+3一体化,儿科学)"))
    assert _name_key("计算机类（计算机科学与技术）") == "计算机类(计算机科学与技术)"
