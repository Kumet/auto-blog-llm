from __future__ import annotations

from typing import Protocol

from domain.models import ArticleBrief, ArticleDraft, ArticlePlan, BatchBrief, OutlineItem, SectionDraft


class LLMPort(Protocol):
    """LLM への依存を抽象化。"""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        ...


class PromptRendererPort(Protocol):
    """各フェーズのプロンプト組み立てを Strategy 化。"""

    def render_plan_prompt(
        self,
        brief: ArticleBrief,
        site_adapter: "SiteAdapterPort",
        existing_titles: list[str] | None = None,
        existing_angles: list[str] | None = None,
        existing_avoid: list[str] | None = None,
    ) -> str:
        ...

    def render_batch_plan_prompt(self, brief: BatchBrief) -> str:
        ...

    def render_section_prompt(
        self,
        plan: ArticlePlan,
        outline_item: OutlineItem,
        previous_sections: list[SectionDraft],
        site_adapter: "SiteAdapterPort",
    ) -> str:
        ...

    def render_qc_soft_prompt(self, draft: ArticleDraft) -> str:
        ...

    def render_revise_prompt(self, draft: ArticleDraft, instructions: list[str], targets: list[str]) -> str:
        ...

    def render_faq_prompt(self, draft: ArticleDraft) -> str:
        ...


class MarkdownRendererPort(Protocol):
    """Markdown -> HTML 変換を抽象化。"""

    def to_html(self, markdown: str) -> str:
        ...


class SiteAdapterPort(Protocol):
    """サイト固有の設定/パース/トーンをカプセル化。"""

    def normalize_slug(self, slug: str) -> str:
        ...

    def apply_site_tone(self, prompt: str) -> str:
        ...

    def parse_plan_response(self, raw: str) -> ArticlePlan:
        ...

    def parse_section_response(self, raw: str, outline_item: OutlineItem) -> SectionDraft:
        ...

    def revise_required(self, draft: ArticleDraft) -> bool:
        ...

    def extend_wp_payload(self, draft: ArticleDraft, payload: dict) -> dict:
        """サイト固有のカテゴリ/タグ/カスタムフィールドを上書き・追加するための拡張ポイント。"""
        ...


class JobStorePort(Protocol):
    """ジョブ状態の永続化を抽象化。"""

    def create(self, job: "JobState") -> None:
        ...

    def get(self, job_id: str) -> "JobState | None":
        ...

    def update(self, job: "JobState") -> None:
        ...
