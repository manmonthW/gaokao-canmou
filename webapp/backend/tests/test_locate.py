"""定位服务单测：覆盖顶部桶、分数缺口、位次超范围等边界。

通过 monkeypatch 替换 app.db 的 fetch_all/fetch_one，不依赖真实数据库。
"""
import asyncio
import pytest

from app.services import locate

# 模拟一份「一分一段表」：分数降序 (score, count, cumulative_rank, is_top_bucket, source)
# 关键边界：
#  - 720 为顶部桶（is_top_bucket=True），cumulative_rank=5
#  - 700 与 680 之间缺 690（分数缺口）
#  - 680 与 400 之间为长缺口
#  - 400 为最低分，cumulative_rank=30 即总人数
FAKE_RANK = [
    (720, 5, 5, True, "lntest"),
    (700, 10, 15, False, "lntest"),
    (680, 12, 27, False, "lntest"),
    (400, 3, 30, False, "lntest"),
]
TOTAL = 30  # 最低分累计 = 总人数

LINES = {"本科": 400, "专科": 150, "特殊类型": 500}


@pytest.fixture
def patch_rank(monkeypatch):
    async def fake_fetch_all(sql, params=None):
        # 按 SQL 区分：一分一段表返回多列，跨年查询返回单列 (year,)
        if "DISTINCT YEAR" in sql.upper():
            return [(2024,), (2023,)]
        if "SCORE_RANK" in sql.upper():
            return list(FAKE_RANK)
        return []

    async def fake_fetch_one(sql, params=None):
        return None

    monkeypatch.setattr(locate.db, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(locate.db, "fetch_one", fake_fetch_one)


@pytest.fixture
def patch_line(monkeypatch):
    async def fake_fetch_all(sql, params=None):
        if "DISTINCT YEAR" in sql.upper():
            return [(2024,), (2023,)]
        if "SCORE_RANK" in sql.upper():
            return list(FAKE_RANK)
        return []

    async def fake_fetch_one(sql, params=None):
        # 特殊类型线查询把 line_type 写死在 SQL 里、参数只有 3 个，
        # 用 SQL 内容判断；其余取 params[3] 的 line_type。
        if "特殊类型" in sql:
            return (LINES["特殊类型"], None)
        lt = params[3] if params and len(params) >= 4 else "本科"
        return (LINES.get(lt, 400), None)

    monkeypatch.setattr(locate.db, "fetch_all", fake_fetch_all)
    monkeypatch.setattr(locate.db, "fetch_one", fake_fetch_one)


# ----------------------------- score_to_rank -----------------------------

def test_score_to_rank_exact(patch_rank):
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 700))
    assert r["found"] is True
    assert r["score"] == 700
    assert r["rank"] == 15
    assert r["rank_range"] == [6, 15]          # cum-cnt+1 .. cum
    assert r["same_score_count"] == 10
    assert r["percentile"] == 50.0             # (30-15)/30*100
    assert r["is_top_bucket"] is False


def test_score_to_rank_top_bucket_above(patch_rank):
    """分数高于顶部桶：归入 X 分及以上区间。"""
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 750))
    assert r["found"] is True
    assert r["is_top_bucket"] is True
    assert r["rank_upper"] == 5
    assert "及以上" in r["note"]


def test_score_to_rank_top_bucket_equal(patch_rank):
    """分数恰等于顶部桶分数：精确命中顶部桶行，标记 is_top_bucket。"""
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 720))
    assert r["found"] is True
    assert r["is_top_bucket"] is True
    assert r["rank"] == 5
    assert r["rank_range"] == [1, 5]


def test_score_to_rank_gap(patch_rank):
    """分数落在缺口（690 无直接行）：给紧邻的位次区间估计。"""
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 690))
    assert r["found"] is True
    assert "rank_range" in r
    # 紧邻更高 700(cum 15) -> 区间 [16, 27]，而非取到顶端的宽松上界
    assert r["rank_range"] == [16, 27]
    assert "区间估计" in r["note"]


def test_score_to_rank_below_table(patch_rank):
    """分数低于全表最低分：标记为低于表，位次大于总人数。"""
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 300))
    assert r["found"] is True
    assert r["below_table"] is True
    assert "低于" in r["note"]
    assert f"大于 {TOTAL}" in r["note"]


def test_score_to_rank_bottom_exact_percentile_zero(patch_rank):
    """最低分精确命中：百分位为 0。"""
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 400))
    assert r["found"] is True
    assert r["rank"] == TOTAL
    assert r["percentile"] == 0.0


def test_score_to_rank_no_data(patch_rank, monkeypatch):
    """一分一段表无数据：优雅返回 found=False。"""
    async def empty(sql, params=None):
        return []
    monkeypatch.setattr(locate.db, "fetch_all", empty)
    r = asyncio.run(locate.score_to_rank(2025, "普通类", "物理学科类", 600))
    assert r["found"] is False
    assert "无一分一段数据" in r["error"]


# ----------------------------- rank_to_score -----------------------------

def test_rank_to_score_zero(patch_rank):
    r = asyncio.run(locate.rank_to_score(2025, "普通类", "物理学科类", 0))
    assert r["found"] is False
    assert "正整数" in r["error"]


def test_rank_to_score_top_bucket(patch_rank):
    """位次落在顶部桶内：返回顶部分数 + 及以上提示。"""
    r = asyncio.run(locate.rank_to_score(2025, "普通类", "物理学科类", 3))
    assert r["found"] is True
    assert r["score"] == 720
    assert r["is_top_bucket"] is True
    assert r["score_note"] == "720 及以上"


def test_rank_to_score_in_bucket(patch_rank):
    """位次落在某分数桶内：返回该分数。"""
    r = asyncio.run(locate.rank_to_score(2025, "普通类", "物理学科类", 15))
    assert r["found"] is True
    assert r["score"] == 700
    assert r.get("is_top_bucket") is not True


def test_rank_to_score_out_of_range(patch_rank):
    """位次超出全表范围：标记超出。"""
    r = asyncio.run(locate.rank_to_score(2025, "普通类", "物理学科类", 100))
    assert r["found"] is True
    assert r["below_table"] is True
    assert "超出" in r["note"]
    assert str(TOTAL) in r["note"]


# ----------------------------- judge_line -----------------------------

def test_judge_line_pass_with_special(patch_line):
    """普通类 + 本科批：同时给出本科线与特殊类型线。"""
    r = asyncio.run(locate.judge_line(
        2025, "普通类", "物理学科类", 520, batch="本科批"))
    assert "error" not in r
    assert r["primary"]["line_type"] == "本科"
    assert r["primary"]["passed"] is True
    assert r["primary"]["gap"] == 120
    assert "special_type" in r
    assert r["special_type"]["passed"] is True
    assert r["special_type"]["gap"] == 20


def test_judge_line_art_note(patch_line):
    """艺术/体育类：仅判断文化课线，并提示专业线。"""
    r = asyncio.run(locate.judge_line(
        2025, "艺术类", "物理学科类", 300, batch="本科批"))
    assert r["primary"]["passed"] is False
    assert r["note"] is not None
    assert "仅判断文化课" in r["note"]


def test_judge_line_missing_target(patch_rank):
    """未提供 batch/line_type：返回错误提示。"""
    r = asyncio.run(locate.judge_line(
        2025, "普通类", "物理学科类", 500))
    assert "error" in r


# ----------------------------- personal_summary 集成 -----------------------------

def test_personal_summary_integration(patch_line):
    """输入分数+位次+批次：返回 by_score / cross_year / line。"""
    r = asyncio.run(locate.personal_summary(
        2025, "普通类", "物理学科类", score=520, rank=1000, batch="本科批"))
    assert r["year"] == 2025
    assert r["by_score"]["found"] is True
    assert isinstance(r["cross_year"], list) and len(r["cross_year"]) >= 0
    assert "line" in r
    assert r["line"]["primary"]["passed"] is True
