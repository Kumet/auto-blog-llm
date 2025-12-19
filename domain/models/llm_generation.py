from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field, validator


class ArticleBrief(BaseModel):
    """入力ブリーフ。Plan 生成の起点。"""

    topic: str
    target_site: str
    seed_title: Optional[str] = None
    audience: Optional[str] = None
    purpose: Optional[str] = None
    constraints: Optional[Any] = None

    class Config:
        extra = "forbid"


class BatchBrief(BaseModel):
    """複数記事をまとめて計画するためのブリーフ。"""

    topic: str
    target_site: str
    desired_count: int = 10
    audience: Optional[str] = None
    purpose: Optional[str] = None
    constraints: Optional[Any] = None

    class Config:
        extra = "forbid"


class OutlineH3(BaseModel):
    id: str
    h3: str
    must_include: List[str] = Field(default_factory=list)

    class Config:
        extra = "forbid"

    @validator("id")
    def id_must_have_prefix(cls, value: str) -> str:
        if not value.startswith("h3-"):
            raise ValueError("outline.h3.id must start with 'h3-'")
        return value


class OutlineItem(BaseModel):
    id: str
    h2: str
    intent: str
    focus_keywords: List[str] = Field(default_factory=list)
    must_include: List[str] = Field(default_factory=list)
    must_avoid: List[str] = Field(default_factory=list)
    h3: List[OutlineH3] = Field(default_factory=list)

    class Config:
        extra = "forbid"

    @validator("id")
    def id_must_have_prefix(cls, value: str) -> str:
        if not value.startswith("h2-"):
            raise ValueError("outline.id must start with 'h2-'")
        return value


class ArticlePlan(BaseModel):
    title: str
    slug: str
    meta_description: str
    outline: List[OutlineItem]
    tags_suggestions: List[str] = Field(default_factory=list)
    volatile_topics: List[str] = Field(default_factory=list)
    safe_assertions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None

    class Config:
        extra = "forbid"


class SectionH3Draft(BaseModel):
    id: str
    h3: str
    body: str

    class Config:
        extra = "forbid"


class SectionDraft(BaseModel):
    h2_id: str
    h2: str
    body: str
    h3_blocks: List[SectionH3Draft] = Field(default_factory=list)

    class Config:
        extra = "forbid"


class ArticleDraft(BaseModel):
    title: str
    slug: str
    meta_description: str
    outline: List[OutlineItem]
    markdown: str
    sections: List[SectionDraft] = Field(default_factory=list)
    faq: List[dict] = Field(default_factory=list)
    tags_suggestions: List[str] = Field(default_factory=list)
    volatile_topics: List[str] = Field(default_factory=list)
    safe_assertions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    quality_self_check: Optional["QualitySelfCheck"] = None

    class Config:
        extra = "forbid"


class QualitySelfCheck(BaseModel):
    meta_description_length: int
    markdown_length: int
    h2_count: int
    h3_count: int
    min_h2_length: int
    min_h3_length: int
    faq_count: int
    assertive_language_found: bool
    regenerate_required: bool

    class Config:
        extra = "forbid"


class QcSeverity(str, Enum):
    hard = "hard"
    soft = "soft"


class QcIssue(BaseModel):
    message: str
    severity: QcSeverity
    target_id: Optional[str] = None
    metric: Optional[str] = None

    class Config:
        extra = "forbid"


class QcReport(BaseModel):
    hard_failed: bool
    soft_failed: bool
    issues: List[QcIssue] = Field(default_factory=list)
    measurements: QualitySelfCheck

    class Config:
        extra = "forbid"


class ReviseRequest(BaseModel):
    sections_to_regenerate: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    hard_fail: bool = False

    class Config:
        extra = "forbid"


class BatchPlanItem(BaseModel):
    article_id: str
    title: str
    angle: str
    target_audience: str
    search_intent: str
    differentiator: str
    avoid_overlap_with: List[str] = Field(default_factory=list)
    outline_hint: Optional[List[str]] = None

    class Config:
        extra = "forbid"


class BatchPlan(BaseModel):
    batch_id: str
    items: List[BatchPlanItem]

    class Config:
        extra = "forbid"
