from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report cho baseline phase.

    Pseudo-code:
    1. Gom source summary.
    2. In metrics retrieval/evaluation.
    3. In data quality va freshness.
    4. Ghi markdown vao report_path.
    """
    sections = [
        "# Phase 1 Baseline Report",
        "",
        "## Source",
        f"- API: {source_summary.get('source_api', '')}",
        f"- Query: {source_summary.get('query', '')}",
        f"- Raw records: {source_summary.get('records', 0)}",
        f"- Clean rows: {source_summary.get('clean_rows', 0)}",
        f"- Collection: `{source_summary.get('collection_name', '')}`",
        "",
        "## Evaluation",
        f"- Samples: {metrics.get('samples', 0)}",
        f"- Retrieval hit rate: {metrics.get('retrieval_hit_rate', 0):.3f}",
        f"- Mean token F1: {metrics.get('mean_token_f1', 0):.3f}",
        f"- Judge accuracy: {metrics.get('judge_accuracy', 0):.3f}",
        "",
        "## Quality",
        f"- Status: {quality.get('success', False)}",
        f"- Freshness: {freshness.get('is_fresh', False)}",
        f"- Stale rows: {freshness.get('stale_rows', 0)}/{freshness.get('total_rows', 0)}",
        "",
    ]
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(sections), encoding="utf-8")


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
) -> None:
    """TODO(student): viet markdown report so sanh baseline/corrupted/repaired."""
    report = {
        "baseline": baseline_metrics,
        "corrupted": corrupted_metrics,
        "repaired": repaired_metrics,
        "corrupted_quality": corrupted_quality,
        "repaired_quality": repaired_quality,
        "corrupted_freshness": corrupted_freshness,
        "repaired_freshness": repaired_freshness,
    }
    path = Path(report_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Corruption Comparison Report",
        "",
        "| Phase | Retrieval hit rate | Mean token F1 | Quality | Freshness |",
        "|---|---:|---:|---|---|",
    ]
    for name, metrics, quality, freshness in [
        ("Baseline", baseline_metrics, {}, {}),
        ("Corrupted", corrupted_metrics, corrupted_quality, corrupted_freshness),
        ("Repaired", repaired_metrics, repaired_quality, repaired_freshness),
    ]:
        lines.append(
            f"| {name} | {metrics.get('retrieval_hit_rate', 0):.3f} | "
            f"{metrics.get('mean_token_f1', 0):.3f} | {quality.get('success', '')} | "
            f"{freshness.get('is_fresh', '')} |"
        )
    lines.extend(["", "## Raw payload", "", "```json", json.dumps(report, indent=2), "```", ""])
    path.write_text("\n".join(lines), encoding="utf-8")
