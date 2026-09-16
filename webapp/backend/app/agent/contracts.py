"""结构化输出契约（§8）：与 router 同一栈 Pydantic v2。

包含：
  • 回答契约：AdvisorSection / RecommendedUnit / AdvisorAnswer
  • 七个只读工具的入参 schema（供工具层 validate，也供模型看到工具签名）

工具入参只暴露语义字段，不暴露 SQL/内部结构；字段名与已确认的 service 签名对齐。
"""
from typing import Optional

from pydantic import BaseModel, Field


# ============ 回答契约 ============

class AdvisorSection(BaseModel):
    """回答中的一个小节：标题 + 正文 + 引用的证据 eid。"""

    title: str
    body: str
    evidence_ids: list[str] = Field(default_factory=list)


class RecommendedUnit(BaseModel):
    """推荐的一个院校-专业录取单元（带风险与证据）。"""

    school: str
    major: str
    batch: Optional[str] = None
    rank_last: Optional[int] = None
    risk: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)


class AdvisorAnswer(BaseModel):
    """参谋助手的结构化回答。"""

    summary: str
    sections: list[AdvisorSection] = Field(default_factory=list)
    recommended_units: list[RecommendedUnit] = Field(default_factory=list)
    caveats: list[str] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list)
    needs_clarification: bool = False


# ============ 工具入参 schema ============
# 每个 schema 对应一个只读工具；字段与 service 签名一致。

class LocateRankArgs(BaseModel):
    """locate_rank → locate.rank_context(category, subject, rank, batch=None)"""

    category: str = Field(description="类别，如普通类")
    subject: str = Field(description="学科类，如物理/历史")
    rank: int = Field(gt=0, description="位次（正整数）")
    batch: Optional[str] = Field(default=None, description="批次，可省")


class SearchCandidatesArgs(BaseModel):
    """search_candidates → match.match(...)"""

    year: int = Field(description="考生年份")
    category: str = Field(description="类别，仅支持普通类")
    subject: str = Field(description="学科类，如物理/历史")
    batch: str = Field(description="批次")
    rank: Optional[int] = Field(default=None, gt=0, description="位次")
    score: Optional[int] = Field(default=None, ge=0, description="分数")
    province: Optional[str] = Field(default=None, description="省份筛选")
    city: Optional[str] = Field(default=None, description="城市筛选")
    level: Optional[str] = Field(default=None, description="院校层次筛选")
    major_keyword: Optional[str] = Field(default=None, description="专业关键词")
    risk: Optional[str] = Field(default=None, description="风险等级（保/稳/冲）")
    page: int = Field(default=1, ge=1, description="页码")
    page_size: int = Field(default=30, ge=1, le=100, description="每页条数")


class GetUnitDetailArgs(BaseModel):
    """get_unit_detail → schools.get_school_major(code, major_name, ...)"""

    code: str = Field(description="院校代码")
    major_name: str = Field(description="专业名称")
    major_code: Optional[str] = Field(default=None, description="专业代码，可省")
    year: Optional[int] = Field(default=None, description="年份筛选")
    category: Optional[str] = Field(default=None, description="类别筛选")


class GetSchoolProfileArgs(BaseModel):
    """get_school_profile → schools.get_school(code) + get_school_strength(code)"""

    code: str = Field(description="院校代码")


class GetMajorInfoArgs(BaseModel):
    """get_major_info → major_catalog.get_major_detail(name)"""

    name: str = Field(description="专业名称")


class CheckSubjectReqArgs(BaseModel):
    """check_subject_req → match.build_req_indexes + lookup_reqs"""

    year: int = Field(description="考生年份")
    category: str = Field(description="类别")
    subject: str = Field(description="学科类")
    batch: str = Field(description="批次")
    school: str = Field(description="院校名称或代码")
    major: str = Field(description="专业名称")


class RankSensitivityArgs(BaseModel):
    """rank_sensitivity → match.sensitivity(...)"""

    year: int = Field(description="考生年份")
    category: str = Field(description="类别，仅支持普通类")
    subject: str = Field(description="学科类")
    batch: str = Field(description="批次")
    rank: Optional[int] = Field(default=None, gt=0, description="位次")
    score: Optional[int] = Field(default=None, ge=0, description="分数")
    province: Optional[str] = Field(default=None, description="省份筛选")
    city: Optional[str] = Field(default=None, description="城市筛选")
    level: Optional[str] = Field(default=None, description="院校层次筛选")
    major_keyword: Optional[str] = Field(default=None, description="专业关键词")
