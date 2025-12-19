from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Tuple

from domain.models import (
    ArticleBrief,
    ArticleDraft,
    ArticlePlan,
    OutlineItem,
    OutlineH3,
    QcIssue,
    QcReport,
    QcSeverity,
    QualitySelfCheck,
    ReviseRequest,
    SectionDraft,
    SectionH3Draft,
)
from usecases.ports import LLMPort, PromptRendererPort, SiteAdapterPort


def _embed_h2_with_id(title: str, h2_id: str) -> str:
    return f"## {title} <!-- id:{h2_id} -->"


def _embed_h3_with_id(title: str, h3_id: str) -> str:
    return f"### {title} <!-- id:{h3_id} -->"


def _render_section_markdown(section: SectionDraft) -> str:
    parts = [_embed_h2_with_id(section.h2, section.h2_id), section.body.strip()]
    for h3 in section.h3_blocks:
        parts.append(_embed_h3_with_id(h3.h3, h3.id))
        parts.append(h3.body.strip())
    return "\n".join(parts) + "\n"


def assemble_markdown(plan: ArticlePlan, sections: List[SectionDraft]) -> str:
    """Plan の順序を保持しつつ H2/H3 を結合し、id コメントを埋め込む。"""
    section_map = {s.h2_id: s for s in sections}
    ordered: List[str] = []
    for item in plan.outline:
        section = section_map.get(item.id)
        if not section:
            continue
        ordered.append(_render_section_markdown(section))
    return "\n".join(ordered).strip() + "\n"


def _unicode_len(text: str) -> int:
    return len(text)


def _extract_body_lengths(markdown: str) -> Tuple[List[Tuple[str, int]], List[Tuple[str, int]]]:
    """H2/H3 ごとの本文文字数を集計する。"""
    h2_pattern = re.compile(r"^## (?P<title>.+?) <!-- id:(?P<id>[^>]+) -->\s*$")
    h3_pattern = re.compile(r"^### (?P<title>.+?) <!-- id:(?P<id>[^>]+) -->\s*$")
    h2_lengths: List[Tuple[str, int]] = []
    h3_lengths: List[Tuple[str, int]] = []
    current_h2_id: str | None = None
    current_h2_body: List[str] = []
    current_h3_body: List[str] = []
    in_h3 = False
    current_h3_id: str | None = None
    lines = markdown.splitlines()

    def flush_h3():
        nonlocal current_h3_body, in_h3
        nonlocal current_h3_id
        if current_h3_body and in_h3 and current_h3_id:
            body_text = "".join([l.strip() for l in current_h3_body if l.strip()])
            h3_lengths.append((current_h3_id, _unicode_len(body_text)))
        current_h3_body = []
        in_h3 = False
        current_h3_id = None

    def flush_h2():
        nonlocal current_h2_body, current_h2_id
        if current_h2_id is not None:
            body_text = "".join([l.strip() for l in current_h2_body if l.strip() and not h3_pattern.match(l)])
            h2_lengths.append((current_h2_id, _unicode_len(body_text)))
        current_h2_body = []

    for line in lines:
        h2_match = h2_pattern.match(line)
        if h2_match:
            flush_h3()
            flush_h2()
            current_h2_id = h2_match.group("id")
            in_h3 = False
            continue
        h3_match = h3_pattern.match(line)
        if h3_match:
            flush_h3()
            current_h3_body = []
            in_h3 = True
            current_h3_id = h3_match.group("id")
            continue
        # Accumulate body lines
        if in_h3:
            current_h3_body.append(line)
        if current_h2_id is not None:
            current_h2_body.append(line)

    flush_h3()
    flush_h2()
    return h2_lengths, h3_lengths


def _assertive_language_present(markdown: str) -> bool:
    return bool(re.search(r"(必ず|絶対|断言|保証)", markdown))


def run_qc(draft: ArticleDraft) -> QcReport:
    h2_lengths, h3_lengths = _extract_body_lengths(draft.markdown)
    h2_count = len(h2_lengths)
    h3_count = len(h3_lengths)
    meta_description_length = _unicode_len(draft.meta_description.strip())
    markdown_length = _unicode_len(draft.markdown)
    min_h2_length = min(h2_lengths, key=lambda x: x[1])[1] if h2_lengths else 0
    min_h3_length = min(h3_lengths, key=lambda x: x[1])[1] if h3_lengths else 0
    faq_count = len(draft.faq)

    measurements = QualitySelfCheck(
        meta_description_length=meta_description_length,
        markdown_length=markdown_length,
        h2_count=h2_count,
        h3_count=h3_count,
        min_h2_length=min_h2_length,
        min_h3_length=min_h3_length,
        faq_count=faq_count,
        assertive_language_found=_assertive_language_present(draft.markdown),
        regenerate_required=False,
    )

    issues: List[QcIssue] = []

    if not 80 <= meta_description_length <= 140:
        issues.append(
            QcIssue(
                message=f"メタディス長が範囲外: {meta_description_length}",
                severity=QcSeverity.hard,
                metric="meta_description_length",
            )
        )

    if not 4 <= h2_count <= 8:
        issues.append(
            QcIssue(
                message=f"H2 本数が範囲外: {h2_count}",
                severity=QcSeverity.hard,
                metric="h2_count",
            )
        )

    if min_h2_length < 300:
        target = next((h2_id for h2_id, length in h2_lengths if length == min_h2_length), None)
        issues.append(
            QcIssue(
                message=f"H2 本文が短い ({min_h2_length} 文字)",
                severity=QcSeverity.hard,
                target_id=target,
                metric="min_h2_length",
            )
        )

    for h3_id, length in h3_lengths:
        if length < 80:
            issues.append(
                QcIssue(
                    message=f"H3 本文が短い ({length} 文字)",
                    severity=QcSeverity.hard,
                    target_id=h3_id,
                    metric="h3_length",
                )
            )
        elif length < 120:
            issues.append(
                QcIssue(
                    message=f"H3 本文が短い (Soft) ({length} 文字)",
                    severity=QcSeverity.soft,
                    target_id=h3_id,
                    metric="h3_length",
                )
            )

    if measurements.assertive_language_found:
        issues.append(
            QcIssue(
                message="断定的な表現が検出されました",
                severity=QcSeverity.soft,
                metric="assertive_language_found",
            )
        )

    outline_ids = {item.id for item in draft.outline}
    missing_ids = [oid for oid in outline_ids if f"id:{oid}" not in draft.markdown]
    if missing_ids:
        for oid in missing_ids:
            issues.append(
                QcIssue(
                    message=f"Markdown に outline id が見つかりません: {oid}",
                    severity=QcSeverity.hard,
                    target_id=oid,
                    metric="outline_id",
                )
            )
    h3_outline_ids = {h3.id for item in draft.outline for h3 in item.h3}
    missing_h3_ids = [hid for hid in h3_outline_ids if f"id:{hid}" not in draft.markdown]
    if missing_h3_ids:
        for hid in missing_h3_ids:
            issues.append(
                QcIssue(
                    message=f"Markdown に H3 id が見つかりません: {hid}",
                    severity=QcSeverity.hard,
                    target_id=hid,
                    metric="outline_h3_id",
                )
            )

    hard_failed = any(issue.severity == QcSeverity.hard for issue in issues)
    soft_failed = any(issue.severity == QcSeverity.soft for issue in issues)
    measurements.regenerate_required = hard_failed

    return QcReport(
        hard_failed=hard_failed,
        soft_failed=soft_failed,
        issues=issues,
        measurements=measurements,
    )


class LLMOrchestrator:
    """Plan → Draft → QC → Revise を連携するオーケストレータ。"""

    def __init__(self, llm: LLMPort, prompt_renderer: PromptRendererPort, site_adapter: SiteAdapterPort):
        self.llm = llm
        self.prompt_renderer = prompt_renderer
        self.site_adapter = site_adapter

    def plan_article(self, brief: ArticleBrief) -> ArticlePlan:
        prompt = self.prompt_renderer.render_plan_prompt(brief, self.site_adapter)
        prompt = self.site_adapter.apply_site_tone(prompt)
        raw = self.llm.complete(prompt, temperature=0.2)
        plan = self.site_adapter.parse_plan_response(raw)
        plan.slug = self.site_adapter.normalize_slug(plan.slug)
        return plan

    def draft_section(
        self, plan: ArticlePlan, outline_item: OutlineItem, previous_sections: List[SectionDraft]
    ) -> SectionDraft:
        prompt = self.prompt_renderer.render_section_prompt(plan, outline_item, previous_sections, self.site_adapter)
        prompt = self.site_adapter.apply_site_tone(prompt)
        raw = self.llm.complete(prompt, temperature=0.7)
        return self.site_adapter.parse_section_response(raw, outline_item)

    def draft_article(self, plan: ArticlePlan) -> Tuple[ArticleDraft, QcReport]:
        sections: List[SectionDraft] = []
        for item in plan.outline:
            section = self.draft_section(plan, item, sections)
            sections.append(section)

        markdown = assemble_markdown(plan, sections)
        draft = ArticleDraft(
            title=plan.title,
            slug=plan.slug,
            meta_description=plan.meta_description,
            outline=plan.outline,
            markdown=markdown,
            sections=sections,
            faq=[],
            tags_suggestions=plan.tags_suggestions,
            volatile_topics=plan.volatile_topics,
            safe_assertions=plan.safe_assertions,
            notes=plan.notes,
        )
        qc_report = run_qc(draft)
        draft.quality_self_check = qc_report.measurements
        return draft, qc_report

    def revise(self, draft: ArticleDraft, qc_report: QcReport) -> ReviseRequest:
        reasons = [issue.message for issue in qc_report.issues]
        sections_to_regenerate: List[str] = []
        for issue in qc_report.issues:
            if issue.metric in {"min_h2_length", "outline_id"} and issue.target_id:
                sections_to_regenerate.append(issue.target_id)
            if issue.metric in {"h3_length", "outline_h3_id"} and issue.target_id:
                # regenerate parent H2 as well for simplicity
                parent_h2 = issue.target_id.split("-")[1] if "-" in issue.target_id else None
                if parent_h2:
                    sections_to_regenerate.append(f"h2-{parent_h2}")
        return ReviseRequest(
            sections_to_regenerate=sections_to_regenerate,
            reasons=reasons,
            hard_fail=qc_report.hard_failed,
        )

    def _soft_qc(self, draft: ArticleDraft) -> Dict[str, Any]:
        prompt = self.prompt_renderer.render_qc_soft_prompt(draft)
        raw = self.llm.complete(prompt, temperature=0.0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return {"fix_targets": [], "fix_instructions": {}, "overall_notes": "JSON parse failed"}
        return {
            "fix_targets": data.get("fix_targets", []),
            "fix_instructions": data.get("fix_instructions", {}),
            "overall_notes": data.get("overall_notes", ""),
        }

    def _replace_sections(
        self, base_sections: List[SectionDraft], replacements: List[SectionDraft]
    ) -> List[SectionDraft]:
        replace_map = {s.h2_id: s for s in replacements}
        result: List[SectionDraft] = []
        for sec in base_sections:
            result.append(replace_map.get(sec.h2_id, sec))
        # 追加で新規 id があれば末尾に足す
        for h2_id, sec in replace_map.items():
            if not any(s.h2_id == h2_id for s in result):
                result.append(sec)
        return result

    def _apply_revise(
        self,
        draft: ArticleDraft,
        plan: ArticlePlan,
        targets: List[str],
        instructions: List[str],
    ) -> Tuple[ArticleDraft, QcReport]:
        prompt = self.prompt_renderer.render_revise_prompt(draft, instructions, targets)
        raw = self.llm.complete(prompt, temperature=0.3)
        try:
            data = json.loads(raw)
            sections_data = data.get("sections", [])
        except json.JSONDecodeError:
            sections_data = []
        new_sections: List[SectionDraft] = []
        for s in sections_data:
            try:
                new_sections.append(SectionDraft.parse_obj(s))
            except Exception:
                continue

        merged_sections = self._replace_sections(draft.sections, new_sections)
        markdown = assemble_markdown(plan, merged_sections)
        revised_draft = draft.copy(
            update={
                "markdown": markdown,
                "sections": merged_sections,
                "outline": plan.outline,
                "tags_suggestions": plan.tags_suggestions,
                "volatile_topics": plan.volatile_topics,
                "safe_assertions": plan.safe_assertions,
            }
        )
        qc_report = run_qc(revised_draft)
        revised_draft.quality_self_check = qc_report.measurements
        return revised_draft, qc_report

    # _markdown_to_sections は現在のメインフローでは未使用。必要に応じて残す。

    def generate_faq(self, draft: ArticleDraft) -> List[dict]:
        prompt = self.prompt_renderer.render_faq_prompt(draft)
        raw = self.llm.complete(prompt, temperature=0.2)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return []
        faq = data.get("faq", [])
        return faq if isinstance(faq, list) else []


def create_article_draft(
    orchestrator: LLMOrchestrator,
    brief: ArticleBrief,
) -> Tuple[ArticleDraft, QcReport, ReviseRequest | None]:
    """ユースケースのエントリポイント。Plan→Draft→QC→Revise を実行する。"""
    plan = orchestrator.plan_article(brief)
    draft, qc_report = orchestrator.draft_article(plan)
    if qc_report.hard_failed:
        revise_request = orchestrator.revise(draft, qc_report)
        return draft, qc_report, revise_request

    # Soft QC ループ (最大 2 回)
    max_soft_retries = 2
    for attempt in range(max_soft_retries):
        if not qc_report.soft_failed:
            break
        soft_qc = orchestrator._soft_qc(draft)
        targets = soft_qc.get("fix_targets", [])
        instructions_map: Dict[str, str] = soft_qc.get("fix_instructions", {})
        instructions = [instructions_map.get(t, f"Fix {t}") for t in targets]
        if not targets:
            break
        draft, qc_report = orchestrator._apply_revise(draft, plan, targets, instructions)
        if qc_report.hard_failed:
            revise_request = orchestrator.revise(draft, qc_report)
            revise_request.reasons.append("Soft QC 修正中に Hard fail が発生")
            return draft, qc_report, revise_request

    # FAQ 生成
    draft.faq = orchestrator.generate_faq(draft)
    final_qc = run_qc(draft)
    draft.quality_self_check = final_qc.measurements
    if final_qc.hard_failed:
        revise_request = orchestrator.revise(draft, final_qc)
        revise_request.reasons.append("最終 QC でハード NG")
        return draft, final_qc, revise_request
    if final_qc.soft_failed:
        revise_request = orchestrator.revise(draft, final_qc)
        revise_request.reasons.append("最終 QC でソフト NG (許容可否を判断)")
        return draft, final_qc, revise_request

    return draft, final_qc, None
