from __future__ import annotations

import datetime
from typing import List, Tuple

from domain.models import (
    ArticleBrief,
    BatchBrief,
    BatchPlanItem,
    JobResultItem,
    JobState,
    JobStatus,
)
from infrastructure.wordpress.client import WordPressClient
from usecases.create_drafts import LLMOrchestrator, run_qc
from usecases.ports import JobStorePort


def _now_iso() -> str:
    return datetime.datetime.utcnow().isoformat() + "Z"


def _batch_item_to_brief(item: BatchPlanItem, batch_brief: BatchBrief) -> ArticleBrief:
    return ArticleBrief(
        topic=batch_brief.topic,
        seed_title=item.title,
        target_site=batch_brief.target_site,
        audience=item.target_audience,
        purpose=item.search_intent,
        constraints={
            "angle": item.angle,
            "differentiator": item.differentiator,
            "avoid_overlap_with": item.avoid_overlap_with,
        },
    )


def _collect_existing(plans: List) -> Tuple[List[str], List[str], List[str]]:
    titles = []
    angles: List[str] = []
    avoid: List[str] = []
    for p in plans:
        titles.append(p.title)
        constraints = getattr(p, "constraints", None)
        if isinstance(constraints, dict):
            angle = constraints.get("angle")
            if angle:
                angles.append(angle)
            avoid_overlap = constraints.get("avoid_overlap_with")
            if avoid_overlap and isinstance(avoid_overlap, list):
                avoid.extend(avoid_overlap)
    return titles, angles, avoid


def _append_log(job: JobState, message: str) -> None:
    job.logs.append(message)


def run_batch_job(
    job_id: str,
    batch_brief: BatchBrief,
    orchestrator: LLMOrchestrator,
    wp_client: WordPressClient,
    job_store: JobStorePort,
) -> JobState:
    job = job_store.get(job_id) or JobState(job_id=job_id, status=JobStatus.queued, total=batch_brief.desired_count)
    job.status = JobStatus.running
    job.started_at = _now_iso()
    job.total = batch_brief.desired_count
    job_store.create(job)

    try:
        batch_plan = orchestrator.batch_plan(batch_brief)
        job.total = len(batch_plan.items)
        job_store.update(job)
        successful_plans = []

        for idx, item in enumerate(batch_plan.items):
            brief = _batch_item_to_brief(item, batch_brief)
            existing_titles, existing_angles, existing_avoid = _collect_existing(successful_plans)
            plan = orchestrator.plan_article(
                brief,
                existing_titles=existing_titles,
                existing_angles=existing_angles,
                existing_avoid=existing_avoid,
            )

            draft, qc_report = orchestrator.draft_article(plan)

            # Soft QC / Revise loop (最大 2 回) + FAQ
            if not qc_report.hard_failed:
                for _ in range(2):
                    if not qc_report.soft_failed:
                        break
                    soft_qc = orchestrator._soft_qc(draft)
                    targets = soft_qc.get("fix_targets", [])
                    inst_map = soft_qc.get("fix_instructions", {})
                    instructions = [inst_map.get(t, f"Fix {t}") for t in targets]
                    if not targets:
                        break
                    draft, qc_report = orchestrator._apply_revise(draft, plan, targets, instructions)
                    if qc_report.hard_failed:
                        break

                if not qc_report.hard_failed:
                    draft.faq = orchestrator.generate_faq(draft)
                    qc_report = run_qc(draft)
                    draft.quality_self_check = qc_report.measurements

            result = JobResultItem(index=idx, title=draft.title)

            if qc_report.hard_failed:
                result.draft_ok = False
                result.error = "; ".join([iss.message for iss in qc_report.issues])
                _append_log(job, f"[{idx+1}/{job.total}] Draft failed: {result.error}")
            else:
                result.draft_ok = True
                wp_res = wp_client.create_draft(draft)
                result.wp_ok = wp_res.success
                result.wp_post_id = wp_res.post_id
                result.wp_url = wp_res.url
                result.error = wp_res.error_message
                if result.wp_ok:
                    _append_log(job, f"[{idx+1}/{job.total}] WP draft created: {result.wp_url}")
                else:
                    _append_log(job, f"[{idx+1}/{job.total}] WP draft failed: {result.error}")

            job.results.append(result)
            job.current += 1
            job_store.update(job)
            successful_plans.append(plan)

        job.status = JobStatus.done
        job.finished_at = _now_iso()
        job_store.update(job)
    except Exception as exc:
        _append_log(job, f"Job failed: {exc}")
        job.status = JobStatus.failed
        job.finished_at = _now_iso()
        job_store.update(job)
    finally:
        return job

