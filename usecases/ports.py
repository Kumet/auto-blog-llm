from __future__ import annotations

from typing import Protocol

from domain.models import ArticleBrief, ArticleDraft, ArticlePlan, OutlineItem, SectionDraft


class LLMPort(Protocol):
    """LLM への依存を抽象化。"""

    def complete(self, prompt: str, *, temperature: float = 0.0, max_tokens: int | None = None) -> str:
        ...


class PromptRendererPort(Protocol):
    """各フェーズのプロンプト組み立てを Strategy 化。"""

    def render_plan_prompt(self, brief: ArticleBrief, site_adapter: "SiteAdapterPort") -> str:
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
