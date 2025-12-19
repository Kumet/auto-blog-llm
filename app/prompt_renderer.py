from __future__ import annotations

import json
from pathlib import Path
from string import Template
from typing import List

import yaml

from domain.models import ArticleBrief, ArticleDraft, ArticlePlan, BatchBrief, OutlineItem, SectionDraft
from usecases.ports import PromptRendererPort, SiteAdapterPort


class PromptRenderer(PromptRendererPort):
    """YAML ベースのテンプレートから各フェーズのプロンプトを組み立てる。"""

    def __init__(self, template_path: Path | str | None = None):
        path = Path(template_path) if template_path else Path("app/prompts/default.yaml")
        self.templates = yaml.safe_load(path.read_text(encoding="utf-8"))

    def _render(self, key: str, **ctx: str) -> str:
        template = Template(self.templates[key])
        return template.safe_substitute(**ctx)

    def render_plan_prompt(
        self,
        brief: ArticleBrief,
        site_adapter: SiteAdapterPort,
        existing_titles: List[str] | None = None,
        existing_angles: List[str] | None = None,
        existing_avoid: List[str] | None = None,
    ) -> str:
        constraints = brief.constraints if brief.constraints is not None else "なし"
        return self._render(
            "plan",
            topic=brief.topic,
            audience=brief.audience or "未指定",
            purpose=brief.purpose or "未指定",
            constraints_json=json.dumps(constraints, ensure_ascii=False, indent=2),
            target_site=brief.target_site,
            seed_title=brief.seed_title or "",
            existing_titles=json.dumps(existing_titles or [], ensure_ascii=False),
            existing_angles=json.dumps(existing_angles or [], ensure_ascii=False),
            existing_avoid=json.dumps(existing_avoid or [], ensure_ascii=False),
        )

    def render_batch_plan_prompt(self, brief: BatchBrief) -> str:
        constraints = brief.constraints if brief.constraints is not None else "なし"
        return self._render(
            "batch_plan",
            topic=brief.topic,
            audience=brief.audience or "未指定",
            purpose=brief.purpose or "未指定",
            constraints_json=json.dumps(constraints, ensure_ascii=False, indent=2),
            target_site=brief.target_site,
            desired_count=brief.desired_count,
        )

    def render_section_prompt(
        self,
        plan: ArticlePlan,
        outline_item: OutlineItem,
        previous_sections: List[SectionDraft],
        site_adapter: SiteAdapterPort,
    ) -> str:
        return self._render(
            "section_draft",
            plan_json=json.dumps(plan.dict(), ensure_ascii=False, indent=2),
            outline_item_json=json.dumps(outline_item.dict(), ensure_ascii=False, indent=2),
            previous_sections_json=json.dumps([s.dict() for s in previous_sections], ensure_ascii=False, indent=2),
        )

    def render_qc_soft_prompt(self, draft: ArticleDraft) -> str:
        return self._render(
            "qc_soft",
            draft_json=json.dumps(draft.dict(), ensure_ascii=False, indent=2),
        )

    def render_revise_prompt(self, draft: ArticleDraft, instructions: List[str], targets: List[str]) -> str:
        return self._render(
            "revise",
            draft_json=json.dumps(draft.dict(), ensure_ascii=False, indent=2),
            instructions_json=json.dumps(instructions, ensure_ascii=False, indent=2),
            targets_json=json.dumps(targets, ensure_ascii=False, indent=2),
        )

    def render_faq_prompt(self, draft: ArticleDraft) -> str:
        return self._render(
            "faq",
            draft_json=json.dumps(draft.dict(), ensure_ascii=False, indent=2),
        )
