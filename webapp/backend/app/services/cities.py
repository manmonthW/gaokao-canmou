from typing import Optional
from app import db

async def list_provinces():
    """返回城市画像中真实存在的省级名称，排除城市名和空值。"""
    rows = await db.fetch_all(
        """SELECT DISTINCT province
             FROM cities
            WHERE province IS NOT NULL AND btrim(province) <> ''
            ORDER BY province"""
    )
    return [r[0] for r in rows]


async def list_cities(province: Optional[str] = None, q: Optional[str] = None):
    """列出已收录城市及院校数。

    可按省份过滤；q 为模糊关键词（匹配城市名）。
    返回字段：city, province, region, tier, cluster, gdp, gdp_year, coastal, note, school_count
    """
    where = ["1=1"]
    params = []
    if province:
        # cities.province 使用去后缀口径（如“辽宁”），而 /meta 可能返回“辽宁省”。
        # 同时接受两种写法，避免筛选后出现空结果。
        normalized = province.removesuffix("省").removesuffix("市")
        where.append("c.province IN (%s, %s)")
        params.extend([province, normalized])
    if q:
        where.append("c.city ILIKE %s")
        params.append(f"%{q}%")
    where_sql = " AND ".join(where)
    rows = await db.fetch_all(
        f"""
        SELECT c.city, c.province, c.region, c.tier, c.cluster,
               c.gdp, c.gdp_year, c.coastal, c.note,
               count(sp.code) AS school_count
          FROM cities c
          LEFT JOIN school_profiles sp ON sp.city = c.city
         WHERE {where_sql}
         GROUP BY c.city, c.province, c.region, c.tier, c.cluster,
                  c.gdp, c.gdp_year, c.coastal, c.note
         ORDER BY c.province, c.city
        """,
        params,
    )
    return [
        {
            "city": r[0],
            "province": r[1],
            "region": r[2],
            "tier": r[3],
            "cluster": r[4],
            "gdp": float(r[5]) if r[5] is not None else None,
            "gdp_year": r[6],
            "coastal": r[7],
            "note": r[8],
            "school_count": r[9] or 0,
        }
        for r in rows
    ]


async def get_city(city: str):
    """城市详情：城市画像 + 该城市院校清单。

    返回：
      {
        profile: { city, province, region, tier, cluster, gdp, gdp_year, coastal, note },
        schools: [ { code, name, level, nature, type, is_985, is_211, is_dfc } ]
      }
    未找到返回 None。
    """
    row = await db.fetch_one(
        """
        SELECT city, province, region, tier, cluster, gdp, gdp_year, coastal, note
          FROM cities WHERE city=%s
        """,
        (city,),
    )
    if not row:
        return None
    profile = {
        "city": row[0],
        "province": row[1],
        "region": row[2],
        "tier": row[3],
        "cluster": row[4],
        "gdp": float(row[5]) if row[5] is not None else None,
        "gdp_year": row[6],
        "coastal": row[7],
        "note": row[8],
    }
    schools = [
        {
            "code": r[0],
            "name": r[1],
            "level": r[2],
            "nature": r[3],
            "type": r[4],
            "is_985": r[5],
            "is_211": r[6],
            "is_dfc": r[7],
        }
        for r in await db.fetch_all(
            """
            SELECT s.code, s.name, sp.level, sp.nature, sp.type,
                   sp.is_985, sp.is_211, sp.is_dfc
              FROM schools s
              JOIN school_profiles sp ON sp.code = s.code
             WHERE sp.city = %s
             ORDER BY sp.is_985 DESC, sp.is_211 DESC, sp.level DESC, s.name
            """,
            (city,),
        )
    ]
    return {"profile": profile, "schools": schools}
