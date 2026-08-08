"""产品层 P1 单测：线差法估位 + 区间匹配分档（不依赖真实数据库）。"""
import asyncio

import pytest

from app.services import locate, match as msvc

# 与 test_locate 相同的模拟一分一段表（分数降序）
FAKE_RANK = [
    (720, 5, 5, True, "lntest"),
    (700, 10, 15, False, "lntest"),
    (680, 12, 27, False, "lntest"),
    (400, 3, 30, False, "lntest"),
]
# 历史两年本科线均为 400
FAKE_LINES = [(2025, 400), (2026, 400)]


@pytest.fixture
def patch_estimate(monkeypatch):
    async def fake_fetch_all(sql, params=None):
        up = sql.upper()
        if "BATCH_CONTROL_LINE" in up:
            return list(FAKE_LINES)
        if "SCORE_RANK" in up:
            return list(FAKE_RANK)
        return []

    monkeypatch.setattr(locate.db, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(locate.db, "fetch_one", lambda *a, **k: asyncio.sleep(0, result=None))


# ----------------------------- P1b 线差法估位 -----------------------------

def test_estimate_rank_line_diff(patch_estimate):
    r = asyncio.run(locate.estimate_rank_by_line_diff(
        "普通类", "物理学科类", score=580, mock_line=480))
    assert r["line_diff"] == 100
    assert len(r["per_year"]) == 2
    for p in r["per_year"]:
        # 估计分 = 400 + 100 = 500，落在缺口 → 区间 [28, 30]，保守取 30
        assert p["est_score"] == 500
        assert p["rank"] == 30
        assert p["rank_range"] == [28, 30]
    # 建议区间 = 跨年 [30,30] 外扩 ±10%
    assert r["suggested_interval"] == {"lo": 27, "hi": 33}
    assert "估算" in r["note"]


def test_estimate_rank_invalid_input(patch_estimate):
    r = asyncio.run(locate.estimate_rank_by_line_diff(
        "普通类", "物理学科类", score=0, mock_line=480))
    assert "error" in r


# ----------------------------- P1a 区间匹配分档 -----------------------------

def _cand(best, worst):
    return {"n_years": 2, "best_rank": best, "worst_rank": worst,
            "median_rank": (best + worst) // 2, "span": worst - best,
            "break_detected": False}


def test_risk_at_interval_two_views():
    cfg = msvc.MATCH_CONFIG
    c = _cand(1000, 2000)
    # 乐观位次 800 <= 安全线 850 → 保；悲观位次 1000（=best，未过安全线）→ 稳
    assert msvc._risk_at(c, 800, cfg)[0] == "保"
    assert msvc._risk_at(c, 1000, cfg)[0] == "稳"
    # 悲观位次 2500（劣于 worst）→ 冲
    assert msvc._risk_at(c, 2500, cfg)[0] == "冲"


def test_match_interval_validation_error():
    r = asyncio.run(msvc.match(
        year=2027, category="普通类", subject="物理学科类", batch="本科批",
        rank_lo=5000, rank_hi=4000))
    assert "error" in r and "区间" in r["error"]


# ----------------------------- P4 反馈闭环 -----------------------------

def test_feedback_requires_admitted_order():
    from app.routers import feedback as fb
    req = fb.FeedbackReq(examinee_year=2026, outcome="admitted")
    r = asyncio.run(fb.submit_feedback(req, user=None))
    assert "error" in r


def test_feedback_order_exceeds_plan_total():
    from app.routers import feedback as fb
    req = fb.FeedbackReq(examinee_year=2026, outcome="admitted",
                         admitted_order=5, plan_total=3)
    r = asyncio.run(fb.submit_feedback(req, user=None))
    assert "error" in r


def test_feedback_ok_anonymous(monkeypatch):
    from app.routers import feedback as fb

    async def fake_add(row):
        # 匿名提交：user_id 必须为 None（真实标签集不携带身份信息）
        assert row["user_id"] is None
        return 42

    monkeypatch.setattr(fb.user_db, "add_feedback", fake_add)
    req = fb.FeedbackReq(examinee_year=2026, outcome="admitted",
                         admitted_order=37, admitted_risk="保",
                         plan_total=112, examinee_rank=1355)
    r = asyncio.run(fb.submit_feedback(req, user=None))
    assert r["ok"] is True and r["id"] == 42


# ----------------------------- P5 偏好最小版 -----------------------------

def _item(risk, diff, school_tier=3, city_tier=None):
    return {"risk": risk, "rank_diff_last": diff,
            "school_tier": school_tier, "city_tier": city_tier}


def test_pref_sort_key_level_within_same_risk():
    a = _item("稳", 100, school_tier=3)   # 普通院校但位次更接近
    b = _item("稳", 500, school_tier=0)   # 985 但位次差更大
    # level 偏好：985 排前；风险档仍优先于偏好
    assert msvc._pref_sort_key(b, "level") < msvc._pref_sort_key(a, "level")
    # certainty 默认：位次差小者排前
    assert msvc._pref_sort_key(a, None) < msvc._pref_sort_key(b, None)
    # 风险档优先级不受偏好影响：保档永远排在稳档前
    c = _item("保", 9000, school_tier=3)
    assert msvc._pref_sort_key(c, "level") < msvc._pref_sort_key(b, "level")


def test_pref_sort_key_city_tier_order():
    a = _item("稳", 500, city_tier="三线")
    b = _item("稳", 100, city_tier="新一线")
    assert msvc._pref_sort_key(b, "city") < msvc._pref_sort_key(a, "city")
    # 未知城市分级排最后
    u = _item("稳", 10, city_tier=None)
    assert msvc._pref_sort_key(u, "city") > msvc._pref_sort_key(a, "city")


# ---------- 冲稳保边界治理：保档子档与 过深保底/超冲 标记 ----------

def test_safe_band_segments():
    """保档三分段：<=R×1.5 标准保底；(1.5R, 3R] 极稳垫底；>3R 过深；边界归浅档。"""
    cfg = msvc.MATCH_CONFIG
    R = 10000
    core = int(R * cfg["safe_band_core"])
    lim = R * cfg["over_safe_ratio"]
    assert msvc._safe_band("保", int(R * 1.2), R, cfg) == "标准保底"
    assert msvc._safe_band("保", core, R, cfg) == "标准保底"        # 边界归标准
    assert msvc._safe_band("保", core + 1, R, cfg) == "极稳垫底"
    assert msvc._safe_band("保", lim, R, cfg) == "极稳垫底"          # 边界归极稳
    assert msvc._safe_band("保", lim + 1, R, cfg) == "过深保底"
    assert msvc._safe_band("稳", lim * 10, R, cfg) is None           # 非保档无子档
    assert msvc._safe_band("保", None, R, cfg) is None


def test_over_safe_flag_boundary():
    """过深保底：仅保档且 best > R×over_safe_ratio（严格大于）时标记。"""
    cfg = msvc.MATCH_CONFIG
    R = 10000
    lim = R * cfg["over_safe_ratio"]
    assert msvc._over_safe("保", lim, R, cfg) is False
    assert msvc._over_safe("保", lim + 1, R, cfg) is True
    assert msvc._over_safe("稳", lim * 10, R, cfg) is False


def test_over_reach_flag_boundary():
    """超冲：仅冲档且 best < R×over_reach_ratio（严格小于）时标记。"""
    cfg = msvc.MATCH_CONFIG
    R = 10000
    lim = int(R * cfg["over_reach_ratio"])
    assert msvc._over_reach("冲", lim, R, cfg) is False
    assert msvc._over_reach("冲", lim - 1, R, cfg) is True
    assert msvc._over_reach("保", 1, R, cfg) is False


def test_pref_sort_certainty_nearest_first():
    """最接近匹配原则：同档内 |位次差| 小者靠前——保档浅（好）保底先于深保底，
    而不是带符号 diff 升序导致的「最深垫底校排最前」。"""
    shallow = _item("保", -100)    # 领先门槛不多 → 最好的保底
    deep = _item("保", -5000)      # 领先门槛很多 → 深保底
    assert msvc._pref_sort_key(shallow, None) < msvc._pref_sort_key(deep, None)
    # 冲档仍是距离近（最现实的冲刺）靠前
    near_reach = _item("冲", 300)
    far_reach = _item("冲", 3000)
    assert msvc._pref_sort_key(near_reach, None) < msvc._pref_sort_key(far_reach, None)
    # 同距离时院校层次高者靠前
    near985 = _item("稳", 200, school_tier=0)
    nearOrd = _item("稳", -200, school_tier=3)
    assert msvc._pref_sort_key(near985, None) < msvc._pref_sort_key(nearOrd, None)
    # 偏好模式次键同样用接近度：level 模式同层次内浅保底先于深保底
    assert msvc._pref_sort_key(shallow, "level") < msvc._pref_sort_key(deep, "level")
