#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""院校/专业实力模块冒烟（任务 #8/#9/#11，migration 0014）。

参照 etl/smoke_xk_api.py 模式，纯 stdlib、无状态、断言失败即退出非零：
  1. /api/v1/meta 含 strength_dictionary（11 条，软科 ruanke third_party=true）；
  2. /api/v1/schools/{code}/strength：北京大学(0001)/辽宁大学(0140) 结构与非空断言；
     eval5_a 行仅允许 verify_status='verified'（services/schools.py 过滤口径）；
  3. /api/v1/match（物理学科类/本科批）：候选含 strength_tags / major_strength，
     且至少命中一所带标签院校；
  4. 未知院校 strength 端点 404；
  5. golden JSON 契约：meta / schools/{code} / match 既有键集合与顺序不变，
     新键（meta.strength_dictionary；schools.strength；
     match item 的 strength_tags/major_strength）必须位于对象末尾；
  6. 性能粗测：/match 全量查询 warm 响应时间（3 次取样取最快）。
     既有基线约 5s（任务 #11 实测改动前后同口径），仅拦截 >8s 显著劣化；
     ≥2s 输出告警与基线说明。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

BASE = "http://127.0.0.1:8000/api/v1"

# ---------- golden 契约：既有键集合与顺序（取自改动前契约） ----------
META_KEYS = ["years", "examinee_year", "last_year", "history_years",
             "categories", "subjects", "batches", "batches_by_category",
             "score_kinds", "provinces", "levels", "natures", "types",
             "flags", "major_flags"]          # 新增 strength_dictionary 在末尾
SCHOOL_KEYS = ["code", "name", "profile", "city", "yearly_summary",
               "majors"]                       # 新增 strength 在末尾
MATCH_TOP_KEYS = ["data_version", "examinee", "interval", "totals",
                  "totals_lo", "excluded_by_subject", "excluded_first",
                  "excluded_re", "subject_requirements_loaded",
                  "classification_note", "batch_context", "facets", "page",
                  "page_size", "items"]        # 顶层无新增键
# 改动前(7b96da1~1) match item 键列表（git 历史证据）：既有键集合与顺序
ITEM_KEYS_PRE = ["school_code", "school_name", "major_code", "major_name",
                 "catalog_name", "batch", "province", "city", "level",
                 "nature", "type", "school_tier", "city_tier", "flags",
                 "n_years", "has_both_years", "best_rank", "worst_rank",
                 "median_rank", "last_year", "last_year_rank",
                 "last_year_score", "span", "relative_vol", "continuous",
                 "break_detected", "risk", "risk_reason", "over_safe",
                 "over_reach", "safe_band", "safe_line", "rank_diff_last",
                 "warning", "yearly"]
# 本次 commit 允许的 match item 新键（is_985/is_211 为 commit 声明的
# 「匹配页 985/211 标签」；strength 两键必须位于末尾）
ITEM_NEW_KEYS = {"is_985", "is_211", "strength_tags", "major_strength"}


def get_json(url):
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.load(r)


def check_keys(label, actual, expected_old, new_keys):
    """断言：既有键集合与顺序逐位不变，新键只允许追加在对象末尾。"""
    assert list(actual[:len(expected_old)]) == expected_old, \
        f"{label}: 既有键集合/顺序被改动: {list(actual)}"
    assert list(actual[len(expected_old):]) == new_keys, \
        f"{label}: 新增键缺失或未位于末尾: {list(actual)}"
    print(f"  [契约] {label}: 既有 {len(expected_old)} 键顺序不变，"
          f"新键 {new_keys} 位于末尾 OK")


# ---------- 1. /meta：strength_dictionary ----------
meta = get_json(BASE + "/meta")
check_keys("meta", list(meta.keys()), META_KEYS, ["strength_dictionary"])
sd = meta["strength_dictionary"]
assert len(sd) == 11, f"strength_dictionary 应 11 条，实际 {len(sd)}"
rk = [r for r in sd if r["tag"].startswith("软科") or "ruanke" in str(r.get("source_note", ""))]
ruanke_rows = [r for r in sd if "软科" in (r.get("source_note") or "")
               or r.get("kind") == "major_ranking"]
assert rk or ruanke_rows, f"未找到软科词表行: {sd}"
for r in (rk or ruanke_rows):
    assert r["third_party"] is True, f"软科行 third_party 应为 true: {r}"
for r in sd:
    assert set(r.keys()) == {"tag", "label", "kind", "third_party",
                             "source_note", "display_order"}, \
        f"strength_dictionary 行结构异常: {r}"
print(f"  [1] meta.strength_dictionary 11 条，软科 third_party=true OK")
print(f"      tags: {[r['tag'] for r in sd]}")

# ---------- 2. /schools/{code}/strength ----------
for code, name, expect_disc in (("0001", "北京大学", True),
                                ("0140", "辽宁大学", True)):
    st = get_json(f"{BASE}/schools/{code}/strength")
    assert set(st.keys()) == {"code", "disciplines", "majors",
                              "strength_tags"}, f"{name} strength 键异常: {st.keys()}"
    assert st["code"] == code
    assert st["strength_tags"], f"{name} strength_tags 为空"
    assert st["majors"], f"{name} majors 为空"
    if expect_disc:
        assert st["disciplines"], f"{name} disciplines 为空"
    for d in st["disciplines"]:
        assert set(d.keys()) == {"discipline_name", "source", "data_year",
                                 "grade", "official", "verify_status"}
        # eval5_a 非官方来源：只允许已人工核验（verified）的行对外
        if d["source"] == "eval5_a":
            assert d["verify_status"] == "verified", \
                f"{name} eval5_a 未核验行泄漏: {d}"
        assert d["verify_status"] == "verified" or d["official"] is True, \
            f"{name} 非法行（未核验且非官方）: {d}"
    for m in st["majors"]:
        assert set(m.keys()) == {"major_name", "major_code", "source",
                                 "data_year", "batch", "rank", "tier", "note"}
    print(f"  [2] {name}({code}): disc={len(st['disciplines'])} "
          f"majors={len(st['majors'])} tags={st['strength_tags']} OK")

# ---------- 3. /match：strength_tags / major_strength ----------
qs = urllib.parse.urlencode({
    "year": 2026, "category": "普通类", "subject": "物理学科类",
    "batch": "本科批", "score": 600, "rank": 12000,
    "page": 1, "page_size": 50})
t0 = time.perf_counter()
match = get_json(BASE + "/match?" + qs)
match_elapsed = time.perf_counter() - t0
check_keys("match 顶层", list(match.keys()), MATCH_TOP_KEYS, [])
items = match["items"]
assert items, "match 候选为空"
for it in items:
    keys = list(it.keys())
    # strength 两键必须位于对象末尾
    assert keys[-2:] == ["strength_tags", "major_strength"], \
        f"match item strength 新键未位于末尾: {keys}"
    # 既有键相对顺序不变（新键仅限声明集合）
    old_part = [k for k in keys if k not in ITEM_NEW_KEYS]
    assert old_part == ITEM_KEYS_PRE, \
        f"match item 既有键集合/顺序被改动: {keys}"
    assert set(keys) - set(ITEM_KEYS_PRE) <= ITEM_NEW_KEYS, \
        f"match item 出现未声明新键: {set(keys) - set(ITEM_KEYS_PRE)}"
    assert isinstance(it["strength_tags"], list)
    assert isinstance(it["major_strength"], list)
print(f"  [契约] match item: 既有 {len(ITEM_KEYS_PRE)} 键相对顺序不变，"
      f"新键 {sorted(ITEM_NEW_KEYS)}，strength 两键位于末尾 OK")
tagged = [it for it in items if it["strength_tags"]]
ms_hit = [it for it in items if it["major_strength"]]
assert tagged, "首页 50 条无一带 strength_tags，未命中带标签院校"
print(f"  [3] match: items={len(items)} 带标签院校={len(tagged)} "
      f"major_strength 命中={len(ms_hit)} OK")
print(f"      样例: {tagged[0]['school_name']} tags={tagged[0]['strength_tags']}")

# ---------- 4. 未知院校 404 ----------
try:
    get_json(BASE + "/schools/ZZZZ/strength")
    raise AssertionError("未知院校 strength 应返回 404")
except urllib.error.HTTPError as e:
    assert e.code == 404, f"未知院校应 404，实际 {e.code}"
print("  [4] 未知院校 strength -> 404 OK")

# ---------- 5. schools/{code} golden 契约 ----------
detail = get_json(BASE + "/schools/0001")
check_keys("schools/{code}", list(detail.keys()), SCHOOL_KEYS, ["strength"])
assert detail["strength"]["strength_tags"], "schools 详情内嵌 strength 为空"
print(f"  [5] schools/0001 契约 OK（内嵌 strength 非空）")

# ---------- 6. 性能粗测（warm 口径：3 次取样，取最小值） ----------
# 任务 #11 实测：改动前(7b96da1~1 于 :8011)与改动后同口径均约 5s——慢为
# 既有基线（全候选 1.8w+ 分档开销），strength 特性仅引入 ~0.5s 以内、
# 不显著；故此处只拦截显著劣化(>8s)，>=2s 输出告警与基线说明。
timings = []
for _ in range(3):
    t0 = time.perf_counter()
    get_json(BASE + "/match?" + qs)
    timings.append(time.perf_counter() - t0)
best = min(timings)
assert best < 8.0, f"/match warm 最快 {best:.3f}s 显著劣化（3 次: {timings}）"
if best >= 2.0:
    print(f"  [6][WARN] /match warm 最快={best:.3f}s ≥2s——改动前基线同口径"
          f"亦约 5s（既有性能基线，非本次改动引入）")
else:
    print(f"  [6] /match warm 最快={best:.3f}s (<2s) OK")
print(f"      warm 3 次={['%.3fs' % t for t in timings]}；"
      f"首次冷启动={match_elapsed:.3f}s（仅参考）")

print("smoke_strength ALL PASS")
