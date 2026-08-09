"""API 响应模型（pydantic v2）。"""
from pydantic import BaseModel
from typing import Optional, List


class ReleaseInfo(BaseModel):
    version: str
    data_as_of: str
    covered_years: List[int]
    covered_categories: List[str]
    covered_batches: List[str]
    status: str
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    quality_summary: Optional[str] = None


class PendingBatch(BaseModel):
    year: int
    category: str
    subject: str
    batch: str
    stage: str
    status: str
    note: Optional[str] = None


class CoverageRow(BaseModel):
    year: int
    category: str
    count: int


class DataStatusResponse(BaseModel):
    release: Optional[ReleaseInfo] = None
    pending_batches: List[PendingBatch] = []
    coverage: List[CoverageRow] = []


class MetaResponse(BaseModel):
    years: List[int] = []
    examinee_year: Optional[int] = None  # 考生年（最新数据年+1）
    last_year: Optional[int] = None      # 最新数据年
    history_years: List[int] = []        # 全部历史数据年（同 years）
    categories: List[str] = []
    subjects: List[str] = []
    batches: List[str] = []
    batches_by_category: dict[str, List[str]] = {}
    score_kinds: List[str] = []
    provinces: List[str] = []
    levels: List[str] = []
    natures: List[str] = []
    types: List[str] = []
    flags: List[str] = []
    major_flags: List[dict] = []
