"""只读工具层（§7）：7 个工具，每个四步——

  1. Pydantic 校验入参（contracts 里的 *Args）
  2. 调已有 service（进程内，无 HTTP，不暴露 SQL）
  3. 裁剪（由 EvidenceLedger 写入时内置）
  4. 写证据账本 → 返回带 eid 的紧凑结果

build_tools(ledger, profile) -> list[BaseTool]：每个工具闭包持有 ledger（写证据）
与 profile（考生上下文，供默认 category/subject/year/batch）。

analyze_plan / search_policy 不在本批（Phase 2/3）。
"""
from typing import Any, Optional

from langchain_core.tools import BaseTool, StructuredTool

from app.agent.contracts import (
    CheckSubjectReqArgs,
    GetMajorInfoArgs,
    GetSchoolProfileArgs,
    GetUnitDetailArgs,
    LocateRankArgs,
    RankSensitivityArgs,
    SearchCandidatesArgs,
)
from app.agent.evidence import EvidenceLedger
from app import db
from app.services import locate, match, schools
from app.services import major_catalog


def _pick(explicit: Optional[Any], profile: dict, key: str) -> Any:
    """显式入参优先，否则回退到考生上下文 profile。"""
    if explicit is not None:
        return explicit
    return (profile or {}).get(key)


def build_tools(ledger: EvidenceLedger, profile: dict | None = None) -> list[BaseTool]:
    """构造绑定了 ledger 与 profile 的 7 个只读工具。

    profile 可包含：category / subject / year / batch / rank / province / city 等考生上下文，
    工具入参未给时回退到它们，减少模型重复传参。
    """
    profile = profile or {}

    async def locate_rank(
        category: str, subject: str, rank: int, batch: Optional[str] = None
    ) -> dict:
        a = LocateRankArgs(category=category, subject=subject, rank=rank, batch=batch)
        data = await locate.rank_context(a.category, a.subject, a.rank, batch=a.batch)
        eid = ledger.add("locate_rank", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def search_candidates(
        year: int,
        category: str,
        subject: str,
        batch: str,
        rank: Optional[int] = None,
        score: Optional[int] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        level: Optional[str] = None,
        major_keyword: Optional[str] = None,
        risk: Optional[str] = None,
        page: int = 1,
        page_size: int = 30,
    ) -> dict:
        a = SearchCandidatesArgs(
            year=year,
            category=category,
            subject=subject,
            batch=batch,
            rank=rank,
            score=score,
            province=province,
            city=city,
            level=level,
            major_keyword=major_keyword,
            risk=risk,
            page=page,
            page_size=page_size,
        )
        data = await match.match(
            year=a.year,
            category=a.category,
            subject=a.subject,
            batch=a.batch,
            rank=a.rank,
            score=a.score,
            province=a.province,
            city=a.city,
            level=a.level,
            major_keyword=a.major_keyword,
            risk=a.risk,
            page=a.page,
            page_size=a.page_size,
        )
        eid = ledger.add("search_candidates", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def get_unit_detail(
        code: str,
        major_name: str,
        major_code: Optional[str] = None,
        year: Optional[int] = None,
        category: Optional[str] = None,
    ) -> dict:
        a = GetUnitDetailArgs(
            code=code,
            major_name=major_name,
            major_code=major_code,
            year=year,
            category=category,
        )
        data = await schools.get_school_major(
            a.code,
            a.major_name,
            major_code=a.major_code,
            year=a.year,
            category=a.category,
        )
        eid = ledger.add("get_unit_detail", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def get_school_profile(code: str) -> dict:
        a = GetSchoolProfileArgs(code=code)
        base = await schools.get_school(a.code)
        strength = await schools.get_school_strength(a.code)
        data = {"school": base, "strength": strength}
        eid = ledger.add("get_school_profile", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def get_major_info(name: str) -> dict:
        a = GetMajorInfoArgs(name=name)
        data = await major_catalog.get_major_detail(a.name)
        eid = ledger.add("get_major_info", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def check_subject_req(
        year: int,
        category: str,
        subject: str,
        batch: str,
        school: str,
        major: str,
    ) -> dict:
        a = CheckSubjectReqArgs(
            year=year,
            category=category,
            subject=subject,
            batch=batch,
            school=school,
            major=major,
        )
        # 选科要求行仅依赖年份（与 match.py 内联查询一致）；category/subject/batch 用于后续匹配语义。
        req_rows = await db.fetch_all(
            """SELECT school_code, school_name, major_name, first_req, re_req
               FROM subject_requirements WHERE year=%s""",
            (a.year,),
        )
        idx = match.build_req_indexes(req_rows)
        pairs, level, school_known = match.lookup_reqs(idx, a.school, a.major)
        data = {
            "pairs": pairs,
            "match_level": level,
            "school_known": school_known,
        }
        eid = ledger.add("check_subject_req", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    async def rank_sensitivity(
        year: int,
        category: str,
        subject: str,
        batch: str,
        rank: Optional[int] = None,
        score: Optional[int] = None,
        province: Optional[str] = None,
        city: Optional[str] = None,
        level: Optional[str] = None,
        major_keyword: Optional[str] = None,
    ) -> dict:
        a = RankSensitivityArgs(
            year=year,
            category=category,
            subject=subject,
            batch=batch,
            rank=rank,
            score=score,
            province=province,
            city=city,
            level=level,
            major_keyword=major_keyword,
        )
        data = await match.sensitivity(
            year=a.year,
            category=a.category,
            subject=a.subject,
            batch=a.batch,
            rank=a.rank,
            score=a.score,
            province=a.province,
            city=a.city,
            level=a.level,
            major_keyword=a.major_keyword,
        )
        eid = ledger.add("rank_sensitivity", a.model_dump(exclude_none=True), data)
        return {"eid": eid, "data": data}

    specs = [
        (locate_rank, "locate_rank", "定位位次对应的当年与历年等效分、控线参照。", LocateRankArgs),
        (search_candidates, "search_candidates", "按考生位次/分数与筛选条件检索院校-专业候选（仅普通类）。", SearchCandidatesArgs),
        (get_unit_detail, "get_unit_detail", "查看单个院校-专业录取单元的历年分数/位次明细。", GetUnitDetailArgs),
        (get_school_profile, "get_school_profile", "查看院校画像与学科实力标签。", GetSchoolProfileArgs),
        (get_major_info, "get_major_info", "查看专业详情：学科评估、趋势、热度画像。", GetMajorInfoArgs),
        (check_subject_req, "check_subject_req", "校验某院校某专业的选科要求是否匹配考生。", CheckSubjectReqArgs),
        (rank_sensitivity, "rank_sensitivity", "位次上下浮动时候选数量的敏感度试算。", RankSensitivityArgs),
    ]

    tools: list[BaseTool] = []
    for func, name, desc, args_schema in specs:
        tools.append(
            StructuredTool.from_function(
                coroutine=func,
                name=name,
                description=desc,
                args_schema=args_schema,
            )
        )
    return tools
