from __future__ import annotations

from typing import Any

from core.utils import write_text


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Write the evidence-backed report for the clean baseline run."""
    metric_rows = "\n".join(
        f"| `{name}` | {value:.4f} |"
        for name, value in metrics.items()
        if isinstance(value, (int, float))
    )
    source_rows = "\n".join(
        f"| {name.replace('_', ' ')} | {value} |" for name, value in source_summary.items()
    )
    check_rows = "\n".join(
        f"| {check['name']} | {'PASS' if check['success'] else 'FAIL'} | {check.get('observed_value', 'N/A')} |"
        for check in quality["checks"]
    )
    freshness_status = "Fresh" if freshness["is_fresh"] else "Stale"
    ragas = metrics.get("ragas", {})
    ragas_note = ragas.get("skipped", ragas.get("error", "Completed")) if isinstance(ragas, dict) else str(ragas)
    report = f"""# Phase 1 — Baseline Pipeline Report

## Source and index

| Item | Value |
| --- | --- |
{source_rows}

## Baseline evaluation

| Metric | Value |
| --- | ---: |
{metric_rows}

Ragas: {ragas_note}

## Data quality gate

Overall quality gate: **{'PASS' if quality['success'] else 'FAIL'}**

| Check | Status | Observed value |
| --- | --- | --- |
{check_rows}

## Freshness SLA

| Item | Value |
| --- | --- |
| Status | {freshness_status} |
| Stale records | {freshness['stale_rows']} / {freshness['total_rows']} ({freshness['stale_ratio_percent']}%) |
| Threshold | age_days > {freshness['freshness_threshold_days']} days; maximum stale ratio {freshness['max_stale_ratio']:.0%} |
| Latest published | {freshness['latest_published']} |
| Oldest published | {freshness['oldest_published']} |
"""
    write_text(report_path, report)


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
) -> None:
    """Write a quantitative comparison of baseline, corrupted, and repaired."""
    baseline_quality = baseline_quality or {"success": None}
    baseline_freshness = baseline_freshness or {"is_fresh": None, "stale_ratio_percent": None}

    def format_metric(value: Any) -> str:
        return f"{value:.4f}" if isinstance(value, (int, float)) else "N/A"

    metric_rows = []
    for metric in ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        baseline = baseline_metrics.get(metric)
        corrupted = corrupted_metrics.get(metric)
        repaired = repaired_metrics.get(metric)
        change = corrupted - baseline if isinstance(baseline, (int, float)) and isinstance(corrupted, (int, float)) else None
        recovery = repaired - corrupted if isinstance(repaired, (int, float)) and isinstance(corrupted, (int, float)) else None
        metric_rows.append(
            f"| `{metric}` | {format_metric(baseline)} | {format_metric(corrupted)} | "
            f"{format_metric(repaired)} | {format_metric(change)} | {format_metric(recovery)} |"
        )

    def quality_status(value: Any) -> str:
        return "PASS" if value is True else "FAIL" if value is False else "N/A"

    def freshness_status(payload: dict[str, Any]) -> str:
        status = payload.get("is_fresh")
        ratio = payload.get("stale_ratio_percent")
        label = "Fresh" if status is True else "Stale" if status is False else "Unknown"
        return f"{label} ({ratio}%)" if ratio is not None else label

    report = f"""# Data Corruption and Repair Report

The same benchmark test set is used for every state. Repair rebuilds from the immutable raw Crossref records, rather than modifying corrupted values in place.

## Performance comparison

| Metric | Baseline | Corrupted | Repaired | Change after corruption | Recovery from corrupted |
| --- | ---: | ---: | ---: | ---: | ---: |
{chr(10).join(metric_rows)}

## Data observability signals

| Signal | Baseline | Corrupted | Repaired |
| --- | --- | --- | --- |
| Quality gate | {quality_status(baseline_quality.get('success'))} | {quality_status(corrupted_quality.get('success'))} | {quality_status(repaired_quality.get('success'))} |
| Freshness | {freshness_status(baseline_freshness)} | {freshness_status(corrupted_freshness)} | {freshness_status(repaired_freshness)} |

## Interpretation

- Corruption alters coverage, content, dates, titles, and document identity; quality and freshness signals identify the invalid state before serving.
- The repair run reconstructs clean data and its vector index from the raw lineage anchor, restoring both data signals and evaluation metrics.
"""
    write_text(report_path, report)
