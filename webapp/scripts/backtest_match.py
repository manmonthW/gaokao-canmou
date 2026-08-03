"""匹配模型回测（Phase 2 前置诊断脚本）。

数据现状：仅有 2025、2026 两年投档最低分。无法做严格「前一年训练→后一年预测」
的滚动回测（训练侧需要 >=2 年，而最早一年 2025 只有 1 年可训练）。
因此本脚本聚焦两类可用于阈值调参的诊断：

  1) 跨年稳定性：同单元 2025↔2026 位次变动分布，以及高波动样本占比，
     用于校准 MATCH_CONFIG.high_vol_rel / high_vol_abs / break_multiplier。
  2) 门槛敏感度：以「考生位次 = 2025 投档位次」模拟申请人，用 2026 投档位次作为
     「是否实际可录取」的近似真值（最新年是最佳可得代理），对比不同保/稳边界
     margin 下各档的真实录取率，用于校准 risk 分档边界。

重要：MVP 不显示概率；本脚本仅输出统计，供人工调参，不产生候选概率。
"""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))) + "/backend")

from app import db  # noqa: E402


async def load_units(category: str, subject: str, batch: str):
    """返回以 (school, major, batch) 为键、含 2025/2026 位次的单元列表。"""
    rows = await db.fetch_all(
        """SELECT a.school_code, a.school_name, a.major_code, a.major_name,
                  a.batch, a.year, a.lowest_rank
           FROM admission_scores a
           WHERE a.category=%s AND a.subject=%s AND a.batch=%s
             AND a.is_collection = FALSE
             AND a.score_kind = '投档最低分'
             AND a.lowest_rank IS NOT NULL""",
        (category, subject, batch),
    )
    units: dict = {}
    for sc, sn, mc, mn, bt, y, lr in rows:
        key = (sc, mc or mn, bt)
        u = units.setdefault(key, {
            "school": sn, "major": mn, "batch": bt,
            "ranks": {},
        })
        u["ranks"][y] = lr
    return [u for u in units.values() if 2025 in u["ranks"] and 2026 in u["ranks"]]


def stability_report(units):
    deltas = []
    vol = 0
    for u in units:
        r25, r26 = u["ranks"][2025], u["ranks"][2026]
        rel = abs(r26 - r25) / r25 if r25 else 0
        deltas.append(rel)
        if rel >= 0.5:  # 与 high_vol_rel 对齐
            vol += 1
    deltas.sort()
    n = len(deltas)
    med = deltas[n // 2] if n else 0
    p90 = deltas[min(n - 1, int(n * 0.9))]
    return {
        "n": n,
        "median_rel_delta": med,
        "p90_rel_delta": p90,
        "high_vol_rate": vol / n if n else 0,
    }


def margin_sensitivity(units, margins=(0.85, 0.9, 0.95, 1.0)):
    """以 2025 位次为申请人位次，2026 位次为近似真值，统计各档录取率。"""
    out = {}
    for m in margins:
        tier_hit = {"保": [0, 0], "稳": [0, 0], "冲": [0, 0]}
        for u in units:
            r25, r26 = u["ranks"][2025], u["ranks"][2026]
            # 用 2025 单年作为「已知历史」模拟分类（best=worst=med=r25）
            R = r25
            if R <= r25 * m:
                tier = "保"
            elif R <= r25:  # R<=med(=r25) 且 > best*m 已在上一支；此处 R<=r25 即 R<=med
                tier = "稳"
            else:
                tier = "冲"
            admitted = R <= r26
            tier_hit[tier][0] += int(admitted)
            tier_hit[tier][1] += 1
        out[m] = {k: (v[0] / v[1] if v[1] else None) for k, v in tier_hit.items()}
    return out


async def main():
    db.init_pool()
    print("=" * 70)
    print("匹配模型回测诊断（2025↔2026 投档最低位次）")
    print("=" * 70)
    for subject in ("物理学科类", "历史学科类"):
        for batch in ("本科批", "专科批"):
            units = await load_units("普通类", subject, batch)
            if not units:
                continue
            print(f"\n### {subject} / {batch}  （两年均有样本 {len(units)} 个单元）")
            st = stability_report(units)
            print(f"  跨年位次相对变动：中位 {st['median_rel_delta']:.1%} | "
                  f"P90 {st['p90_rel_delta']:.1%} | 高波动(≥50%)占比 {st['high_vol_rate']:.1%}")
            sens = margin_sensitivity(units)
            print("  保档边界敏感度（2025位次→2026实际可录率）：")
            for m, tiers in sens.items():
                parts = "  ".join(
                    f"{k}={('-' if t is None else f'{t:.0%}')}" for k, t in tiers.items()
                )
                print(f"    margin={m}: {parts}")
    print("\n说明：2026 为最新可得年份，作为「是否可录取」的近似真值；")
    print("      保档边界 margin 越大越保守。结合上表校准 MATCH_CONFIG。")
    db.close_pool()


if __name__ == "__main__":
    asyncio.run(main())
